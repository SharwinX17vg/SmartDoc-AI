# SmartDoc AI Architecture

The extension is a thin client. It owns only user interaction and sends PDFs/questions to the FastAPI REST API.

```text
Popup UI -> /api/v1/documents -> PDF extraction -> page-aware chunks
                                      -> embedding provider -> vector index
Popup UI -> /api/v1/query     -> hybrid retrieval -> answer provider -> citations
```

## Extension boundary

`extension/popup` contains the Version 1 UI. `background` and `content` are reserved for later browser workflows and are intentionally empty in this foundation.

## Backend boundaries

- `document_processing`: PDF parsing and chunk construction.
- `rag`: embedding and retrieval interfaces/implementations.
- `services`: application orchestration and answer/command behavior.
- `api`: HTTP schemas and routes.

The local `TfidfEmbeddingModel` is the initial vector adapter. It is deterministic and install-light for development; the `EmbeddingProvider` protocol gives us a stable replacement point for dense embeddings later. The persisted JSON index is likewise a small MVP adapter, not a commitment to a specific production vector database.
