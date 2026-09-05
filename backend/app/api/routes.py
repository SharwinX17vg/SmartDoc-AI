from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.schemas import DocumentBatchResponse, QueryRequest, QueryResponse, ShareRequest, ShareResponse, SharedAnswer, UploadResponse
from ..services.answer_service import AnswerService
from ..services.document_service import DocumentService
from ..services.share_service import ShareService

router = APIRouter(prefix="/api/v1")
document_service: DocumentService | None = None
answer_service: AnswerService | None = None
share_service: ShareService | None = None


def configure_services(documents: DocumentService, answers: AnswerService, shares: ShareService) -> None:
    global document_service, answer_service, share_service
    document_service = documents
    answer_service = answers
    share_service = shares


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/documents", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service is not ready")
    content = await file.read()
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a readable PDF")
    try:
        return document_service.ingest(file.filename, content)
    except ValueError as error:
        status_code = 413 if "limit" in str(error).lower() or "exceeds" in str(error).lower() else 400
        raise HTTPException(status_code=status_code, detail="SmartDoc could not process this PDF: " + str(error)) from error


@router.post("/documents/batch", response_model=DocumentBatchResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> DocumentBatchResponse:
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service is not ready")
    uploaded, failures = [], []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            failures.append(f"{file.filename or 'unnamed file'}: only PDF files are supported")
            continue
        try:
            content = await file.read()
            if not content.startswith(b"%PDF"):
                failures.append(f"{file.filename}: the uploaded file is not a readable PDF")
                continue
            result = document_service.ingest(file.filename, content)
            uploaded.append(result)
        except ValueError as error:
            failures.append(f"{file.filename}: {error}")
    return DocumentBatchResponse(uploaded=uploaded, failures=failures)


@router.get("/documents")
def list_documents():
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service is not ready")
    return {"documents": document_service.list_documents()}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str):
    if document_service is None or not document_service.remove(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "removed", "document_id": document_id}


@router.post("/documents/clear")
def clear_documents():
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service is not ready")
    document_service.clear()
    return {"status": "cleared"}


@router.post("/query", response_model=QueryResponse)
def query_document(request: QueryRequest) -> QueryResponse:
    if answer_service is None:
        raise HTTPException(status_code=503, detail="Answer service is not ready")
    answer, command, intent, sources, documents_used = answer_service.answer(
        request.question, request.top_k, request.selected_document_ids, request.conversation
    )
    return QueryResponse(answer=answer, command=command, intent=intent, sources=sources, documents_used=documents_used)


@router.post("/share", response_model=ShareResponse)
def create_share(request: ShareRequest):
    if share_service is None:
        raise HTTPException(status_code=503, detail="Share service is not ready")
    return share_service.create(request)


@router.get("/share/{share_id}", response_model=SharedAnswer)
def get_share(share_id: str):
    if share_service is None:
        raise HTTPException(status_code=503, detail="Share service is not ready")
    shared = share_service.get(share_id)
    if shared is None:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    return shared
