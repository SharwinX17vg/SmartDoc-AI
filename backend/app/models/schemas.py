from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    document_name: str
    page_number: int
    chunk_text: str
    score: float


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)


class QueryResponse(BaseModel):
    answer: str
    command: str | None = None
    sources: list[SourceReference]


class UploadResponse(BaseModel):
    document_id: str
    document_name: str
    page_count: int
    chunk_count: int
