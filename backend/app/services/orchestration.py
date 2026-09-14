from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class ResponseSpec:
    style: str = "direct"
    depth: str = "standard"
    audience: str = "general"
    format: str = "natural"
    preferences: tuple[str, ...] = ()

    def instructions(self) -> str:
        parts = [
            f"Response style: {self.style}.",
            f"Response depth: {self.depth}.",
            f"Audience: {self.audience}.",
            f"Preferred format: {self.format}.",
        ]
        if self.preferences:
            parts.append("Session preferences: " + ", ".join(self.preferences) + ".")
        return " ".join(parts)


@dataclass(frozen=True)
class RequestPlan:
    task: str
    retrieval_query: str
    generation_question: str
    spec: ResponseSpec
    follow_up: bool = False
    source_mode: str = "documents"
    topic: str = ""
    entities: tuple[str, ...] = ()
    page_scope: tuple[int, int] | None = None
    multipart: bool = False
    clarification_needed: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


def build_request_plan(
    question: str,
    conversation: list[dict[str, str]] | None = None,
) -> RequestPlan:
    text = " ".join(question.split())
    lowered = text.lower()
    history = _valid_history(conversation)
    follow_up = _is_follow_up(lowered)
    preferences = _preferences(history)
    spec = _response_spec(lowered, preferences)
    task = _task(lowered)
    page_scope = _page_scope(lowered)
    topic = _topic(text)
    entities = tuple(_entities(text))
    multipart = _is_multipart(lowered)
    clarification_needed = len(text.split()) < 3 and not follow_up
    reference = _reference_context(history) if follow_up else ""
    retrieval_query = f"{reference} {text}".strip() if reference else text
    generation_question = f"{text}\n\n{spec.instructions()}"
    if reference:
        generation_question += f"\nResolved conversation context: {reference}"
    return RequestPlan(
        task=task,
        retrieval_query=retrieval_query,
        generation_question=generation_question,
        spec=spec,
        follow_up=follow_up,
        metadata={"source": "selected_documents"},
        topic=topic,
        entities=entities,
        page_scope=page_scope,
        multipart=multipart,
        clarification_needed=clarification_needed,
    )


def retrieval_queries(plan: RequestPlan) -> list[str]:
    queries = [plan.retrieval_query]
    if plan.task in {"summary", "important_topics", "overview"}:
        queries.append("main purpose key concepts important topics conclusion")
    elif plan.task == "comparison":
        queries.append(plan.retrieval_query + " differences similarities advantages limitations")
    elif plan.task == "location":
        queries.append(plan.retrieval_query + " page section definition")
    elif plan.task in {"teaching", "study_plan", "quiz", "flashcards", "notes", "revision", "exam", "viva", "interview"}:
        queries.append(plan.retrieval_query + " definitions key concepts examples common mistakes")
    return list(dict.fromkeys(query for query in queries if query.strip()))


def _task(question: str) -> str:
    if any(term in question for term in ("summar", "overview", "what is this document about")):
        return "summary" if "summar" in question else "overview"
    if any(term in question for term in ("important", "main topics", "what should i study", "key points")):
        return "important_topics"
    if any(term in question for term in ("compare", "difference", "similar", "which one")):
        return "comparison"
    if any(term in question for term in ("what page", "which page", "where did you get", "locate")):
        return "location"
    if any(term in question for term in ("keyword", "key terms")):
        return "keywords"
    if any(term in question for term in ("flashcard", "flash cards", "flash cards")):
        return "flashcards"
    if any(term in question for term in ("quiz me", "make a quiz", "practice quiz", "mcq")):
        return "quiz"
    if any(term in question for term in ("study plan", "study schedule", "revision plan")):
        return "study_plan"
    if any(term in question for term in ("make notes", "take notes", "notes from")):
        return "notes"
    if any(term in question for term in ("revise", "revision", "recap")):
        return "revision"
    if "viva" in question:
        return "viva"
    if any(term in question for term in ("interview", "mock interview")):
        return "interview"
    if any(term in question for term in ("teach me", "teaching mode", "teach this")):
        return "teaching"
    if any(term in question for term in ("explain", "why", "how", "teach", "don't understand", "example")):
        return "explanation"
    if any(term in question for term in ("exam", "marks", "mark answer")):
        return "exam"
    return "question"


def _response_spec(question: str, preferences: tuple[str, ...]) -> ResponseSpec:
    style = "explanatory" if any(term in question for term in ("explain", "teach", "why", "how")) else "direct"
    depth = "standard"
    if re.search(r"\b2[- ]?mark\b|one line|briefly|short answer|make it short", question):
        depth = "brief"
    elif re.search(r"\b(5|10)[- ]?mark\b|detailed|properly|full explanation|tell me more", question):
        depth = "detailed"
    audience = "beginner" if any(term in question for term in ("simple", "easier", "beginner", "don't understand")) else "general"
    if "exam" in question:
        audience = "learner"
        style = "exam-ready"
    if any(term in question for term in ("teach", "quiz", "flashcard", "study plan", "viva", "interview", "revision")):
        audience = "learner"
        style = "study-oriented"
    if "example" in question:
        response_format = "example"
    else:
        response_format = "bullets" if any(term in question for term in ("points", "steps", "list")) else "natural"
    return ResponseSpec(style, depth, audience, response_format, preferences)


def _is_follow_up(question: str) -> bool:
    return bool(re.match(
        r"^(it|this|that|they|them|the above|previous|same|again|continue|next|why|how|"
        r"what does|what is it|what about|explain that|make it|tell me more|give me an example|i don't understand)\b",
        question,
    ))


def _valid_history(conversation: list[dict[str, str]] | None) -> list[dict[str, str]]:
    return [
        item for item in (conversation or [])[-8:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]


def _reference_context(history: list[dict[str, str]]) -> str:
    for item in reversed(history):
        content = " ".join(item["content"].split())
        if item["role"] == "assistant" and content:
            return content[:700]
    return ""


def _preferences(history: list[dict[str, str]]) -> tuple[str, ...]:
    preferences: list[str] = []
    user_text = " ".join(item["content"].lower() for item in history if item["role"] == "user")
    if user_text.count("simple") >= 2 or user_text.count("easier") >= 2:
        preferences.append("prefer simple explanations")
    if user_text.count("short") >= 2 or user_text.count("brief") >= 2:
        preferences.append("prefer concise answers")
    if user_text.count("detailed") >= 2:
        preferences.append("prefer detailed answers")
    return tuple(preferences)


def _page_scope(question: str) -> tuple[int, int] | None:
    match = re.search(r"\bpages?\s+(\d+)\s*(?:-|to|through)\s*(\d+)\b", question)
    if match:
        start, end = sorted((int(match.group(1)), int(match.group(2))))
        return start, end
    match = re.search(r"\bpage\s+(\d+)\b", question)
    if match:
        page = int(match.group(1))
        return page, page
    return None


def _topic(question: str) -> str:
    cleaned = re.sub(r"\b(?:please|can you|could you|explain|summarize|tell me about)\b", "", question, flags=re.I)
    return " ".join(cleaned.split()).strip(" ?.")


def _entities(question: str) -> list[str]:
    ignored = {"Compare", "Explain", "Summarize", "What", "Which", "How", "Tell"}
    return [entity for entity in re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", question) if entity not in ignored]


def _is_multipart(question: str) -> bool:
    return len(re.findall(r"\b(?:and|also|plus|then|secondly|firstly)\b", question)) > 0 or "?" in question.rstrip("?")
