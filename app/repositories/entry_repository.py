from abc import ABC, abstractmethod

from app.models.entry import Entry


class EntryRepository(ABC):
    @abstractmethod
    def save(self, entry: Entry) -> None: ...

    @abstractmethod
    def get(self, user_id: str, entry_id: str) -> Entry | None: ...

    @abstractmethod
    def list_by_user(self, user_id: str, from_ts: str | None = None, to_ts: str | None = None) -> list[Entry]: ...

    @abstractmethod
    def get_many(self, user_id: str, entry_ids: list[str]) -> list[Entry]: ...

    @abstractmethod
    def list_by_day(self, user_id: str, month: int, day: int) -> list[Entry]: ...