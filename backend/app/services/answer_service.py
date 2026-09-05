import re

from ..models.schemas import SourceReference
from ..rag.local_index import LocalHybridIndex


class AnswerService:
    def __init__(self, index: LocalHybridIndex) -> None:
        self.index = index

    def answer(self, question: str, top_k: int = 5) -> tuple[str, str | None, list[SourceReference]]:
        command, request = self._parse_command(question)
        matches = self.index.search(request, top_k)
        sources = [
            SourceReference(
                document_name=self.index.document_name,
                page_number=chunk.page_number,
                chunk_text=chunk.text,
                score=round(score, 4),
            )
            for chunk, score in matches
        ]
        if not matches:
            return "I could not find relevant content in the uploaded document.", command, []
        if command == "/keywords":
            answer = self._keywords(matches)
        elif command == "/find":
            answer = "\n\n".join(chunk.text for chunk, _ in matches)
        elif command == "/explain":
            answer = f"Here is a document-grounded explanation:\n\n{matches[0][0].text}"
        else:
            answer = f"Based on the uploaded document:\n\n{matches[0][0].text}"
        return answer, command, sources

    @staticmethod
    def _parse_command(question: str) -> tuple[str | None, str]:
        match = re.match(r"\s*(/\w+)\s*(.*)", question)
        return (match.group(1).lower(), match.group(2).strip()) if match else (None, question)

    @staticmethod
    def _keywords(matches) -> str:
        words: dict[str, int] = {}
        for chunk, _ in matches:
            for word in re.findall(r"[A-Za-z][A-Za-z-]{3,}", chunk.text.lower()):
                words[word] = words.get(word, 0) + 1
        keywords = sorted(words, key=words.get, reverse=True)[:12]
        return "Important terms: " + ", ".join(keywords)
