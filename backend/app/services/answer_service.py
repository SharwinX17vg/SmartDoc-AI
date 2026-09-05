import re
from collections import defaultdict
import logging
import os

from ..models.schemas import DocumentSummary, SourceReference
from ..rag.local_index import LocalHybridIndex
from .answer_provider import AnswerProvider, AnswerProviderError, ExtractiveAnswerProvider, create_answer_provider

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
    ) -> tuple[str, str | None, str, list[SourceReference], list[DocumentSummary]]:
        command, request = self._parse_command(question)
        intent = self._intent(command, request)
        if intent == "casual_chat":
            return self._casual(request), command, intent, [], []
        if conversation and self._is_follow_up(request):
            recent_context = " ".join(item.get("content", "") for item in conversation[-8:] if item.get("content"))
            request = f"{recent_context} {request}".strip()
        candidates = int(os.getenv("RETRIEVAL_CANDIDATES", "15"))
        min_score = float(os.getenv("MIN_RELEVANCE_SCORE", "0.05"))
        final_chunks = int(os.getenv("FINAL_CONTEXT_CHUNKS", str(top_k)))
        candidates = max(candidates, final_chunks)
        matches = self.index.search(request, candidates, document_ids, candidates, min_score)
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
            request,
            context,
            intent,
            conversation,
            command,
            matches,
        )
        return answer, command, intent, sources, self._documents(document_ids, matches)

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
        if re.fullmatch(r"(hi|hello|hey|how are you|thanks|thank you)[!. ]*", lowered): return "casual_chat"
        if any(word in lowered for word in ("compare", "difference", "common between")): return "comparison"
        if any(word in lowered for word in ("summarize", "summary", "important topics", "study all")): return "summary"
        if any(word in lowered for word in ("explain", "how does", "why is", "what does")): return "explanation"
        return "document_question"

    @staticmethod
    def _casual(question: str) -> str:
        lowered = question.lower()
        if "thank" in lowered: return "You're welcome."
        if "how are you" in lowered: return "I'm ready to help you understand your documents."
        return "Hi! I'm SmartDoc AI. Upload one or more documents and ask me anything about them."

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
