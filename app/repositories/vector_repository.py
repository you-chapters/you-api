from abc import ABC, abstractmethod

from app.models.entry_tags import EntryTags


class VectorRepository(ABC):
    @abstractmethod
    def upsert(self, entry_id: str, user_id: str, vector: list[float], timestamp: int, tags: EntryTags | None = None) -> None: ...

    @abstractmethod
    def search(self, user_id: str, vector: list[float], top_k: int = 10) -> list[str]: ...
