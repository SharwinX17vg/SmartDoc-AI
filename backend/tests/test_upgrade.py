from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.document_processing.chunker import DocumentChunk
from app.rag.embeddings import TfidfEmbeddingModel
from app.rag.local_index import LocalHybridIndex
from app.services.answer_provider import (
    AnswerProviderError,
    ExtractiveAnswerProvider,
    LLMAnswerProvider,
    create_answer_provider,
)
from app.services.answer_service import AnswerService
from app.services.orchestration import build_request_plan, retrieval_queries
from app.services.share_service import ShareService


client = TestClient(app)


def test_casual_chat_does_not_need_documents():
    response = client.post("/api/v1/query", json={"question": "Hi"})
    assert response.status_code == 200
    assert response.json()["intent"] == "greeting"
    assert "SmartDoc AI" in response.json()["answer"]


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("hiii", "greeting"),
        ("good morning", "greeting"),
        ("thanks a lot", "thanks"),
        ("bye", "goodbye"),
        ("what is the weather today?", "out_of_scope"),
    ],
)
def test_non_document_intents_do_not_retrieve(question, intent):
    class SpyIndex:
        def search(self, *args, **kwargs):
            raise AssertionError("non-document intent must not retrieve")

        def summaries(self):
            return []

    answer, _, actual_intent, sources, documents = AnswerService(SpyIndex()).answer(question)
    assert actual_intent == intent
    assert answer
    assert sources == []
    assert documents == []


def test_whitespace_question_is_rejected():
    response = client.post("/api/v1/query", json={"question": "   "})
    assert response.status_code == 422


def test_index_scopes_retrieval_to_selected_document(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    first = DocumentChunk("a", "a", "a.pdf", 1, "Intro", "PIC16F877A controller")
    second = DocumentChunk("b", "b", "b.pdf", 2, "Intro", "CNN image model")
    index.add_document("a.pdf", [first], "a")
    index.add_document("b.pdf", [second], "b")
    matches = index.search("controller", document_ids=["b"], top_k=3)
    assert matches == [] or all(chunk.document_id == "b" for chunk, _ in matches)


def test_index_persists_document_metadata_and_size(tmp_path: Path):
    path = tmp_path / "index.json"
    index = LocalHybridIndex(path)
    chunk = DocumentChunk("a", "a", "a.pdf", 1, "Intro", "controller")
    index.add_document("a.pdf", [chunk], "a", size_bytes=1234)
    restored = LocalHybridIndex(path)
    assert restored.summaries()[0]["size_bytes"] == 1234
    assert restored.summaries()[0]["document_name"] == "a.pdf"


def test_invalid_pdf_is_rejected():
    response = client.post("/api/v1/documents", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 400


def test_embedding_falls_back_for_stopword_only_text():
    matrix = TfidfEmbeddingModel().fit_transform(["the and or"])
    assert matrix.shape == (1, 5)


def test_provider_selection_uses_fallback_without_configuration(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert isinstance(create_answer_provider(), ExtractiveAnswerProvider)


def test_provider_selection_uses_openai_when_only_key_is_set(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    provider = create_answer_provider()
    assert isinstance(provider, LLMAnswerProvider)


def test_answer_service_uses_factory_when_provider_is_not_injected(tmp_path: Path, monkeypatch):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document("paper.pdf", [DocumentChunk("a", "a", "paper.pdf", 1, "Intro", "controller")], "a")
    fake = object()
    monkeypatch.setattr("app.services.answer_service.create_answer_provider", lambda: fake)
    assert AnswerService(index).provider is fake


def test_llm_provider_generates_from_source_aware_prompt():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "The controller is PIC16F877A."}}]}).encode()

    provider = LLMAnswerProvider("secret", "test-model", base_url="https://llm.test/v1")
    with patch("app.services.answer_provider.urlopen", return_value=Response()) as request:
        answer = provider.generate("Which controller is used?", "DOCUMENT: paper.pdf\nPAGE: 2\nTEXT: PIC16F877A", "document_question")
    assert answer == "The controller is PIC16F877A."
    sent = json.loads(request.call_args.args[0].data.decode())
    assert "DOCUMENT CONTEXT" in sent["messages"][-1]["content"]
    assert sent["messages"][0]["role"] == "system"
    assert request.call_args.args[0].headers["Authorization"] == "Bearer secret"


def test_request_plan_adapts_follow_up_and_response_requirements():
    plan = build_request_plan(
        "Explain that simply for my exam",
        [
            {"role": "user", "content": "What is ADC?"},
            {"role": "assistant", "content": "ADC converts analog signals into digital values."},
        ],
    )
    assert plan.task == "explanation"
    assert plan.follow_up is True
    assert plan.spec.audience == "learner"
    assert "ADC converts" in plan.retrieval_query
    assert "Response style" in plan.generation_question


def test_task_aware_retrieval_adds_synthesis_query():
    plan = build_request_plan("What are the important things?")
    queries = retrieval_queries(plan)
    assert plan.task == "important_topics"
    assert len(queries) == 2
    assert "important topics" in queries[1]


@pytest.mark.parametrize(
    ("question", "task"),
    [
        ("Teach me this topic", "teaching"),
        ("Make flashcards from this", "flashcards"),
        ("Quiz me on the chapter", "quiz"),
        ("Create a study plan", "study_plan"),
    ],
)
def test_learning_tasks_are_structured_without_general_ai_fallback(question, task):
    plan = build_request_plan(question)
    assert plan.task == task
    assert plan.source_mode == "documents"
    assert plan.spec.audience == "learner"


def test_request_plan_extracts_page_scope_entities_and_multipart_question():
    plan = build_request_plan("Compare ADC and PWM on pages 2 to 4, and explain the difference?")
    assert plan.page_scope == (2, 4)
    assert plan.entities == ("ADC", "PWM")
    assert plan.multipart is True


def test_index_can_limit_retrieval_to_a_page_range(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document(
        "paper.pdf",
        [
            DocumentChunk("a", "a", "paper.pdf", 1, "Intro", "controller overview"),
            DocumentChunk("b", "a", "paper.pdf", 3, "Methods", "controller method"),
        ],
        "a",
    )
    matches = index.search("controller", page_range=(3, 3))
    assert matches
    assert all(chunk.page_number == 3 for chunk, _ in matches)


def test_answer_service_calls_provider_for_explain(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document("paper.pdf", [DocumentChunk("a", "a", "paper.pdf", 1, "Methods", "PWM controls motor speed.")], "a")

    class FakeProvider:
        def generate(self, question, context, intent, conversation=None):
            assert intent == "explanation"
            assert "PAGE: 1" in context
            return "PWM varies the duty cycle to control speed."

    answer, _, _, _, _ = AnswerService(index, FakeProvider()).answer("/explain PWM")
    assert answer == "PWM varies the duty cycle to control speed."


def test_special_modes_use_injected_provider(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document(
        "paper.pdf",
        [DocumentChunk("a", "a", "paper.pdf", 1, "Methods", "PWM controls motor speed and uses a duty cycle.")],
        "a",
    )
    calls = []

    class FakeProvider:
        def generate(self, question, context, intent, conversation=None):
            calls.append((question, intent, context, conversation))
            return f"generated {intent}"

    service = AnswerService(index, FakeProvider())
    for question in ("/keywords PWM", "/find PWM", "/explain PWM", "Summarize PWM", "Compare PWM documents"):
        answer, *_ = service.answer(question)
        assert answer.startswith("generated ")
    assert [call[1] for call in calls] == ["keywords", "search", "explanation", "summary", "comparison"]


def test_normal_question_uses_provider_with_bounded_follow_up_context(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document("paper.pdf", [DocumentChunk("a", "a", "paper.pdf", 1, "Sensors", "The HC-SR04 measures fill level.")], "a")
    captured = {}

    class FakeProvider:
        def generate(self, question, context, intent, conversation=None):
            captured.update(question=question, context=context, intent=intent, conversation=conversation)
            return "The sensor measures distance to determine fill level."

    history = [{"role": "user", "content": "What sensor measures fill level?"}, {"role": "assistant", "content": "The HC-SR04."}]
    answer, *_ = AnswerService(index, FakeProvider()).answer("What does it do?", conversation=history)
    assert answer.startswith("The sensor")
    assert captured["intent"] == "explanation"
    assert "HC-SR04" in captured["question"]
    assert "DOCUMENT: paper.pdf" in captured["context"]
    assert captured["conversation"] == history


def test_answer_service_falls_back_when_llm_fails(tmp_path: Path):
    index = LocalHybridIndex(tmp_path / "index.json")
    index.add_document("paper.pdf", [DocumentChunk("a", "a", "paper.pdf", 1, "Methods", "PWM controls motor speed.")], "a")

    class FailingProvider:
        def generate(self, question, context, intent, conversation=None):
            raise AnswerProviderError("provider unavailable")

    answer, _, _, _, _ = AnswerService(index, FailingProvider()).answer("What does PWM do?")
    assert "PWM controls motor speed" in answer


def test_share_tokens_expire():
    service = ShareService("https://example.test")
    created = service.create(type("Request", (), {"answer": "answer", "sources": [], "expiration_days": 1})())
    assert created.share_url.endswith(created.share_id)
    assert service.get(created.share_id) is not None
    service.items[created.share_id] = service.items[created.share_id].model_copy(
        update={"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
    )
    assert service.get(created.share_id) is None
