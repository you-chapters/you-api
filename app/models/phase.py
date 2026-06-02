from pydantic import BaseModel, model_validator


class PhaseRecord(BaseModel):
    phase_id: str
    title: str
    description: str
    start_date: str
    end_date: str | None
    entry_count: int
    dominant_topics: list[str]
    mean_mood: float
    top_people: list[str]
    top_locations: list[str]
    generated_at: str
    is_open: bool

    @model_validator(mode="after")
    def _open_requires_no_end_date(self) -> "PhaseRecord":
        if self.is_open and self.end_date is not None:
            raise ValueError("is_open=True requires end_date=None")
        return self


class PhaseIndex(BaseModel):
    phase_ids: list[str]
    last_detected_at: str
    window_size_days: int
