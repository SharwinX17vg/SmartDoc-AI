from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.schemas import QueryRequest, QueryResponse, UploadResponse
from ..services.answer_service import AnswerService
from ..services.document_service import DocumentService

router = APIRouter(prefix="/api/v1")
document_service: DocumentService | None = None
answer_service: AnswerService | None = None


def configure_services(documents: DocumentService, answers: AnswerService) -> None:
    global document_service, answer_service
    document_service = documents
    answer_service = answers


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/documents", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service is not ready")
    return document_service.ingest(file.filename, await file.read())


@router.post("/query", response_model=QueryResponse)
def query_document(request: QueryRequest) -> QueryResponse:
    if answer_service is None:
        raise HTTPException(status_code=503, detail="Answer service is not ready")
    answer, command, sources = answer_service.answer(request.question, request.top_k)
    return QueryResponse(answer=answer, command=command, sources=sources)
