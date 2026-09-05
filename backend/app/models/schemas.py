from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    document_id: str | None = None
    document_name: str
    page_number: int
    chunk_id: str | None = None
    section_title: str | None = None
    chunk_text: str = ""
    score: float


class DocumentSummary(BaseModel):
    document_id: str
    document_name: str
    page_count: int
    chunk_count: int


class DocumentBatchResponse(BaseModel):
    uploaded: list[DocumentSummary]
    failures: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)
    selected_document_ids: list[str] | None = None
    conversation: list[dict[str, str]] = Field(default_factory=list, max_length=8)


class QueryResponse(BaseModel):
    answer: str
    command: str | None = None
    intent: str = "document_question"
    sources: list[SourceReference]
    documents_used: list[DocumentSummary] = Field(default_factory=list)


class UploadResponse(BaseModel):
    document_id: str
    document_name: str
    page_count: int
    chunk_count: int


class ShareRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)
    sources: list[SourceReference] = Field(default_factory=list, max_length=10)
    expiration_days: int | None = Field(default=None, ge=1, le=30)


class ShareResponse(BaseModel):
    share_id: str
    share_url: str
    expires_at: str


class SharedAnswer(BaseModel):
    answer: str
    sources: list[SourceReference]
    created_at: str
    expires_at: str
