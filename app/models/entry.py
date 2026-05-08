from pydantic import BaseModel


class CreateEntryRequest(BaseModel):
    user_id: str
    entry: str


class Entry(BaseModel):
    user_id: str
    timestamp: str
    entry_id: str
    entry: str