from pydantic import BaseModel, Field

from app.models.entry import Entry


class QaRequest(BaseModel):
    question: str = Field(..., max_length=1000)


class QaResult(BaseModel):
    answer: str
    sources: list[Entry]
