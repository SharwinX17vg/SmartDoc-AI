import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import configure_services, router
from .rag.local_index import LocalHybridIndex
from .services.answer_service import AnswerService
from .services.answer_provider import create_answer_provider
from .services.document_service import DocumentService
from .services.share_service import ShareService


load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def _cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


app = FastAPI(title="SmartDoc AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

index = LocalHybridIndex(Path(__file__).parents[2] / "data" / "index.json")
document_service = DocumentService(index)
answer_provider = create_answer_provider()
answer_service = AnswerService(index, answer_provider)
share_service = ShareService(os.getenv("PUBLIC_API_ORIGIN", ""))
configure_services(document_service, answer_service, share_service)
app.include_router(router)
