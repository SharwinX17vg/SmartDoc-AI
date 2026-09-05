# SmartDoc AI

SmartDoc AI is a browser extension and FastAPI service for asking grounded questions about uploaded documents.

## Current Version 1 scope

- Manifest V3 popup with multi-PDF selection, document scope, and chat history.
- Page-preserving PDF text extraction.
- Cleaned extraction and metadata-aware chunking.
- Local TF-IDF vector indexing plus exact keyword scoring.
- Candidate retrieval, score filtering, scoped search, and duplicate removal.
- Intent-aware casual chat, document questions, summaries, comparisons, and `/keywords`, `/find`, and `/explain` commands.
- Answers include document name, page number, and retrieved excerpts.
- Copy, download, native share, and expiring backend-backed share tokens.

The answer layer supports a real OpenAI-compatible hosted LLM. When configured, retrieved evidence is sent through a grounding prompt for concise generation. Without valid LLM configuration, SmartDoc logs `Answer provider: Extractive fallback` and uses the dependency-free emergency fallback.

## Architecture

```text
extension/popup -> FastAPI REST API -> document_processing -> scoped hybrid retrieval -> answer service -> sources/share service
```

See [docs/architecture.md](docs/architecture.md) for module boundaries and extension points.

## Setup

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. OpenAPI docs are at `/docs`.

### Environment variables

Copy `.env.example` to `.env` if you need local configuration. `CORS_ORIGINS` is a comma-separated list of allowed web origins. Chrome extension origins are allowed by the backend's extension-origin rule. `LLM_API_KEY` is never committed.

Current configuration variables include `PUBLIC_API_ORIGIN`, upload limits, retrieval limits, `MIN_RELEVANCE_SCORE`, `MAX_CONTEXT_CHARS`, `SHARE_LINK_EXPIRATION_DAYS`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, and `LLM_MAX_TOKENS`.

To activate real generation locally, set `LLM_PROVIDER=openai` and `LLM_API_KEY` in an untracked `.env` file. `LLM_MODEL` defaults to `gpt-4o-mini`, and `LLM_BASE_URL` defaults to `https://api.openai.com/v1`. `OPENAI_API_KEY` and `OPENAI_MODEL` remain supported as compatibility aliases.

### Render deployment

The root [render.yaml](render.yaml) defines the web service. Render can deploy it with:

- Build command: `pip install -r backend/requirements.txt`
- Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/v1/health`

Set `CORS_ORIGINS` in Render to any web origins that should call the API. The Chrome extension is authorized separately by its `chrome-extension://` origin. Render's default filesystem is ephemeral, so the current local index is suitable for an MVP instance but will be lost on redeploy/restart; production persistence requires a database/vector-store adapter or persistent disk.

### Extension

1. Open `chrome://extensions` (or the equivalent Chromium extensions page).
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select the `extension` folder.
4. Start the backend, open the extension popup, select a PDF, and upload it.

The popup reads its API origin from [extension/popup/config.js](extension/popup/config.js). The checked-in configuration points to the current Render service. If the deployment URL changes, update it and the matching `extension/manifest.json` host permission before packaging the extension. The popup displays upload status, answers, and citations.

The current workspace index and share-token store are process-local. Render restarts can lose them, so durable production use requires a persistent database/vector-store adapter. Share links are intentionally opaque and expire, but this MVP does not provide authentication or durable cross-instance storage. Live LLM verification requires a real API key and is intentionally not performed in automated tests.

## API endpoints

- `POST /api/v1/documents`: backward-compatible single PDF upload.
- `POST /api/v1/documents/batch`: partial-success multi-PDF upload.
- `GET /api/v1/documents`: list indexed documents.
- `DELETE /api/v1/documents/{document_id}` and `POST /api/v1/documents/clear`: document lifecycle.
- `POST /api/v1/query`: scoped question, command, summary, comparison, bounded conversation context, and hosted LLM generation when configured.
- `POST /api/v1/share` and `GET /api/v1/share/{share_id}`: minimal expiring shared answers.

## Tests

From `backend` with the virtual environment active:

```powershell
pip install -r requirements-dev.txt
pytest
```

## Roadmap

Future adapters can add a hosted LLM, dense embeddings/vector databases, vision/OCR, webpage and YouTube ingestion, student/exam modes, richer synthesis, GraphRAG, agents, MCP, evaluation, authentication, durable workspaces, and observability without changing the initial popup/API boundaries.
