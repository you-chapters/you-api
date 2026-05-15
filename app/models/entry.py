from pydantic import BaseModel, Field


class CreateEntryRequest(BaseModel):
    entry: str = Field(max_length=10_000)


class Entry(BaseModel):
    user_id: str = Field(max_length=256)
    timestamp: str
    entry_id: str
    entry: str = Field(max_length=10_000)