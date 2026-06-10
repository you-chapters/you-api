from pydantic import BaseModel, Field


class QaRequest(BaseModel):
    question: str = Field(..., max_length=1000)


class QaResult(BaseModel):
    answer: str
    sources: list[str]
