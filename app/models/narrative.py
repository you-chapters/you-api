from typing import Literal

from pydantic import BaseModel


class NarrativeSummary(BaseModel):
    period_type: Literal["week", "month"]
    period_key: str
    entry_count: int
    text: str
    generated_at: str
    is_cached: bool = True
