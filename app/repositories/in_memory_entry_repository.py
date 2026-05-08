from app.models.entry import Entry
from app.repositories.entry_repository import EntryRepository


class InMemoryEntryRepository(EntryRepository):
    def __init__(self) -> None:
        self._store: dict[str, Entry] = {}

    def save(self, entry: Entry) -> None:
        self._store[entry.entry_id] = entry

    def get(self, entry_id: str) -> Entry | None:
        return self._store.get(entry_id)

    def list_by_user(self, user_id: str) -> list[Entry]:
        return [e for e in self._store.values() if e.user_id == user_id]
