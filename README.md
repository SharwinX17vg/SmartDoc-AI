# SmartDoc AI

SmartDoc AI is a browser extension and FastAPI service for asking grounded questions about uploaded documents.

## Current Version 1 scope

- Manifest V3 popup with PDF selection and upload.
- Page-preserving PDF text extraction.
- Configurable text chunking.
- Local TF-IDF vector indexing plus exact keyword scoring.
- Hybrid retrieval before answer generation.
- Normal questions and `/keywords`, `/find`, and `/explain` commands.
- Answers include document name, page number, and retrieved excerpts.

The current answer provider is extractive, so the project runs without an API key. A hosted LLM can be added behind the answer-provider boundary later.

## Architecture

```text
extension/popup -> FastAPI REST API -> document_processing -> rag index/retrieval -> answer service
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

Copy `.env.example` to `.env` if you need local configuration. `CORS_ORIGINS` is a comma-separated list of allowed web origins. Chrome extension origins are allowed by the backend's extension-origin rule. `OPENAI_API_KEY` and `OPENAI_MODEL` are reserved for a future hosted answer provider and are not required by Version 1.

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

The popup reads its API origin from [extension/popup/config.js](extension/popup/config.js). For production, change it to the Render HTTPS origin and keep that exact origin represented in `extension/manifest.json` host permissions before packaging the extension. The popup displays upload status, answers, and citations.

## Tests

From `backend` with the virtual environment active:

```powershell
pip install -r requirements-dev.txt
pytest
```

## Roadmap

Future adapters can add dense embeddings/vector databases, multiple documents, vision/OCR, webpage and YouTube ingestion, student/exam modes, comparison and synthesis, GraphRAG, agents, MCP, evaluation, and observability without changing the initial popup/API boundaries.
