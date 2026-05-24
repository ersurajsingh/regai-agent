from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    session_id: str
    query: str = Field(..., max_length=4000)


class QueryResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    trace_id: str | None = None
