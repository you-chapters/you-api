from abc import ABC, abstractmethod

from app.models.entry import Entry


class EntryRepository(ABC):
    @abstractmethod
    def save(self, entry: Entry) -> None: ...

    @abstractmethod
    def get(self, user_id: str, entry_id: str) -> Entry | None: ...

    @abstractmethod
    def list_by_user(self, user_id: str) -> list[Entry]: ...