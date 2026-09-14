import re
from collections import defaultdict
import logging
import os

from ..models.schemas import DocumentSummary, SourceReference
from ..rag.local_index import LocalHybridIndex
from .answer_provider import AnswerProvider, AnswerProviderError, ExtractiveAnswerProvider, create_answer_provider
from .orchestration import build_request_plan, retrieval_queries

logger = logging.getLogger(__name__)


class AnswerService:
    def __init__(self, index: LocalHybridIndex, provider: AnswerProvider | None = None) -> None:
        self.index = index
        self.provider = provider if provider is not None else create_answer_provider()
        self.fallback = ExtractiveAnswerProvider()

    def answer(
        self,
        question: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
        conversation: list[dict[str, str]] | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> tuple[str, str | None, str, list[SourceReference], list[DocumentSummary]]:
        command, request = self._parse_command(question)
        plan = build_request_plan(request, conversation)
        page_scope = (
            (page_start, page_end or page_start)
            if page_start is not None
            else plan.page_scope
        )
        intent = self._intent(command, request)
        if intent == "document_question":
            intent = {
                "summary": "summary",
                "overview": "summary",
                "important_topics": "summary",
                "comparison": "comparison",
                "explanation": "explanation",
                "teaching": "teaching",
                "study_plan": "study_plan",
                "quiz": "quiz",
                "flashcards": "flashcards",
                "notes": "notes",
                "revision": "revision",
                "exam": "exam",
                "viva": "viva",
                "interview": "interview",
            }.get(plan.task, intent)
        if intent in {"greeting", "thanks", "goodbye", "invalid"}:
            return self._casual(request, intent), command, intent, [], []
        matches = None
        if intent == "out_of_scope":
            # An apparently general question can still be valid when the selected
            # document explicitly contains that subject.
            if not getattr(self.index, "chunks", None):
                return self._casual(request, intent), command, intent, [], []
            probe_score = max(float(os.getenv("MIN_RELEVANCE_SCORE", "0.1")), 0.15)
            matches = self.index.search(
                request,
                top_k=1,
                document_ids=document_ids,
                candidates=1,
                min_score=probe_score,
                page_range=page_scope,
            )
            if not matches:
                return self._casual(request, intent), command, intent, [], []
            intent = "document_question"
        candidates = int(os.getenv("RETRIEVAL_CANDIDATES", "15"))
        min_score = float(os.getenv("MIN_RELEVANCE_SCORE", "0.05"))
        final_chunks = int(os.getenv("FINAL_CONTEXT_CHUNKS", str(top_k)))
        if plan.task in {"summary", "important_topics", "overview"}:
            final_chunks = max(final_chunks, 8)
        candidates = max(candidates, final_chunks)
        if matches is None:
            matches = self._retrieve(
                retrieval_queries(plan),
                candidates,
                document_ids,
                min_score,
                plan.task,
                page_scope,
            )
        matches = self._compress_matches(matches, final_chunks)
        sources = [
            SourceReference(
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                chunk_id=chunk.chunk_id,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                chunk_text=chunk.text,
                score=round(score, 4),
            )
            for chunk, score in matches
        ]
        if not matches:
            return "I couldn't find enough information in the selected documents to answer that accurately.", command, intent, [], self._documents(document_ids)
        context = self._format_context(matches)
        answer = self._generate_or_fallback(
            plan.generation_question,
            context,
            intent,
            conversation,
            command,
            matches,
        )
        return answer, command, intent, sources, self._documents(document_ids, matches)

    def _retrieve(self, queries, candidates, document_ids, min_score, task, page_range=None):
        per_query = max(2, candidates // len(queries))
        found = []
        seen: set[str] = set()
        for query in queries:
            for chunk, score in self.index.search(
                query,
                per_query,
                document_ids,
                candidates,
                min_score,
                page_range,
            ):
                if chunk.chunk_id in seen:
                    continue
                seen.add(chunk.chunk_id)
                found.append((chunk, score))
        found.sort(key=lambda item: item[1], reverse=True)
        if task in {"summary", "important_topics", "overview"}:
            return found[:max(candidates, 8)]
        return found[:candidates]

    @staticmethod
    def _parse_command(question: str) -> tuple[str | None, str]:
        match = re.match(r"\s*(/\w+)\s*(.*)", question)
        return (match.group(1).lower(), match.group(2).strip()) if match else (None, question)

    @staticmethod
    def _intent(command: str | None, question: str) -> str:
        lowered = question.lower().strip()
        if command == "/keywords": return "keywords"
        if command == "/find": return "search"
        if command == "/explain": return "explanation"
        normalized = re.sub(r"[^a-z0-9'\s]", "", lowered)
        if re.fullmatch(r"h+i+", normalized) or normalized in {
            "hi", "hello", "hey", "good morning", "good afternoon",
            "good evening", "how are you", "what's up",
        }:
            return "greeting"
        if normalized in {"thanks", "thank you", "thanks a lot", "okay thanks", "ok thanks"}:
            return "thanks"
        if normalized in {"bye", "goodbye", "see you", "see ya"}:
            return "goodbye"
        if re.fullmatch(r"[a-z]{6,}", normalized) and not re.search(r"[aeiou]", normalized):
            return "invalid"
        if any(phrase in normalized for phrase in (
            "weather today", "news today", "stock price", "tell me a joke",
            "current time", "latest sports score",
        )):
            return "out_of_scope"
        if any(word in lowered for word in ("compare", "difference", "common between")): return "comparison"
        if any(word in lowered for word in ("summarize", "summary", "important topics", "study all")): return "summary"
        if any(word in lowered for word in ("explain", "how does", "why is", "what does")): return "explanation"
        return "document_question"

    @staticmethod
    def _casual(question: str, intent: str) -> str:
        if intent == "thanks":
            return "You're welcome!"
        if intent == "goodbye":
            return "Goodbye! Come back whenever you want to explore your documents."
        if intent == "out_of_scope":
            return "I can answer questions grounded in your uploaded documents."
        if intent == "invalid":
            return "Please ask a clear question about your uploaded documents."
        if "how are you" in question.lower():
            return "I'm ready to help you understand your documents."
        return "Hi! I'm SmartDoc AI. Ask me anything about your uploaded documents."

    @staticmethod
    def _is_follow_up(question: str) -> bool:
        return bool(re.match(r"^(what|why|how|where|when|which|it|they|this|that)\b", question.lower().strip()))

    @staticmethod
    def _direct_answer(matches) -> str:
        text = matches[0][0].text.strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(sentences[:3])

    def _generate_or_fallback(self, question, context, intent, conversation, command, matches) -> str:
        try:
            return self.provider.generate(question, context, intent, conversation)
        except (AnswerProviderError, TimeoutError, OSError) as error:
            logger.warning("LLM answer generation failed; using extractive fallback: %s", error)
            if command == "/keywords":
                return self._keywords(matches)
            if command == "/find":
                return self._find(matches)
            if command == "/explain":
                return self._fallback_explanation(matches)
            if intent == "summary":
                return self._summary(matches)
            if intent == "comparison":
                return self._comparison(matches)
            return self.fallback.generate(
                question,
                "\n".join(chunk.text.strip() for chunk, _ in matches),
                intent,
                conversation,
            )

    @staticmethod
    def _compress_matches(matches, limit):
        seen_sentences: set[str] = set()
        compressed = []
        for chunk, score in matches:
            sentences = []
            for sentence in re.split(r"(?<=[.!?])\s+", chunk.text.strip()):
                normalized = " ".join(sentence.lower().split())
                if normalized and normalized not in seen_sentences:
                    seen_sentences.add(normalized)
                    sentences.append(sentence.strip())
            if sentences:
                compressed.append((chunk.__class__(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    text=" ".join(sentences),
                ), score))
            if len(compressed) >= limit:
                break
        return compressed

    @staticmethod
    def _format_context(matches) -> str:
        parts = []
        max_chars = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))
        total_chars = 0
        for chunk, _ in matches:
            section = chunk.section_title or "Unspecified section"
            part = (
                f"DOCUMENT: {chunk.document_name}\n"
                f"PAGE: {chunk.page_number}\n"
                f"SECTION: {section}\n"
                f"TEXT: {chunk.text.strip()}"
            )
            if total_chars + len(part) > max_chars:
                break
            parts.append(part)
            total_chars += len(part)
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _fallback_explanation(matches) -> str:
        return f"Here is a document-grounded explanation:\n\n{matches[0][0].text}"

    @staticmethod
    def _find(matches) -> str:
        return "\n\n".join(f"{chunk.text.strip()} (Page {chunk.page_number})" for chunk, _ in matches[:3])

    @staticmethod
    def _summary(matches) -> str:
        return "\n".join(f"- {chunk.text.strip().split('.')[0]} (Page {chunk.page_number})" for chunk, _ in matches[:5])

    @staticmethod
    def _comparison(matches) -> str:
        grouped = defaultdict(list)
        for chunk, _ in matches:
            grouped[chunk.document_name].append(chunk.text.strip().split('.')[0])
        return "\n".join(f"**{name}**\n- " + "\n- ".join(values[:3]) for name, values in grouped.items())

    @staticmethod
    def _keywords(matches) -> str:
        words: dict[str, int] = {}
        for chunk, _ in matches:
            for word in re.findall(r"[A-Za-z][A-Za-z-]{3,}", chunk.text.lower()):
                words[word] = words.get(word, 0) + 1
        keywords = sorted(words, key=words.get, reverse=True)[:12]
        return "Important terms: " + ", ".join(keywords)

    def _documents(self, document_ids=None, matches=None) -> list[DocumentSummary]:
        allowed = set(document_ids) if document_ids else None
        names = {chunk.document_id for chunk, _ in matches} if matches else allowed
        return [DocumentSummary(**summary) for summary in self.index.summaries() if names is None or summary["document_id"] in names]
