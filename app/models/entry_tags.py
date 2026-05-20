from pydantic import BaseModel, ConfigDict, Field


class EntryTags(BaseModel):
    model_config = ConfigDict(extra="ignore")

    people: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    mood: str | None = None
    time_markers: list[str] = Field(default_factory=list)
