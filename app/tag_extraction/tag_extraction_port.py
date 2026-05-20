from abc import ABC, abstractmethod

from app.models.entry_tags import EntryTags


class TagExtractionClient(ABC):
    @abstractmethod
    def extract(self, text: str, timestamp: str, user_location: str | None) -> EntryTags: ...
