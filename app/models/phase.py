from pydantic import BaseModel


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


class PhaseIndex(BaseModel):
    phase_ids: list[str]
    last_detected_at: str
    window_size_days: int
