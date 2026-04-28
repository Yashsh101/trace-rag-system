from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class CitationResponse(BaseModel):
    label: str
    chunk_id: int
    document_id: int
    filename: str
    page_start: int | None
    page_end: int | None
    score: float
    snippet: str


class QueryResponse(BaseModel):
    trace_id: str
    query_log_id: int | None = None
    answer: str
    citations: list[CitationResponse]
    no_answer: bool = False
