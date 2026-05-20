from pydantic import BaseModel


class MoodPoint(BaseModel):
    date: str
    mood: str


class TopicCount(BaseModel):
    topic: str
    count: int


class PersonCount(BaseModel):
    name: str
    count: int


class PeriodSummary(BaseModel):
    period_days: int
    entry_count: int
    mood_timeline: list[MoodPoint]
    top_topics: list[TopicCount]
    top_people: list[PersonCount]
