# SmartDoc AI Architecture

The extension is a thin client. It owns only user interaction and sends PDFs/questions to the FastAPI REST API.

```text
Popup UI -> /api/v1/documents -> PDF extraction -> page-aware chunks
                                      -> embedding provider -> vector index
Popup UI -> /api/v1/query     -> request orchestration -> task-aware retrieval -> answer provider -> citations
```

## Extension boundary

`extension/popup` contains the current UI, document manager, chat state, safe answer rendering, and answer actions. `background` and `content` remain reserved for later browser workflows.

## Backend boundaries

- `document_processing`: PDF parsing and chunk construction.
- `rag`: embedding and multi-document retrieval interfaces/implementations.
- `services`: document lifecycle, intent-aware answer behavior, and share-token orchestration.
- `services/orchestration.py`: converts natural requests and bounded conversation context into a
  task plan, response requirements, follow-up reference, and retrieval query variants.
- `api`: HTTP schemas and routes.

The local `TfidfEmbeddingModel` is the initial vector adapter. It is deterministic and install-light for development; the `EmbeddingProvider` protocol gives us a stable replacement point for dense embeddings later. The persisted JSON index is likewise a small MVP adapter, not a commitment to a specific production vector database. Retrieval can scope results to selected document IDs, retrieve a configurable candidate set, filter by score, and remove duplicate text before answer formatting.

The answer service classifies casual messages before retrieval, builds an orchestration plan for
response style/depth/audience, expands retrieval for synthesis tasks, resolves bounded follow-up
references, compresses evidence, and returns concise source metadata. `create_answer_provider()`
selects `LLMAnswerProvider` only when `LLM_PROVIDER` and an API key are configured; otherwise it
logs and selects `ExtractiveAnswerProvider`. Provider failures are logged and fall back safely
without exposing provider details.

`LLMAnswerProvider` uses an OpenAI-compatible `/chat/completions` endpoint. Its system prompt labels retrieved text as `DOCUMENT CONTEXT - DATA ONLY`, includes document/page/section metadata, rejects empty or malformed responses, and supplies only bounded recent conversation history.

Share tokens contain only the submitted answer and source references, use opaque random IDs, and expire. The in-memory store is suitable for a single MVP process only; durable deployment requires a persistent store and authentication policy.
