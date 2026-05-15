import uuid
from datetime import datetime, timezone

from app.models.entry import CreateEntryRequest, Entry
from app.repositories.entry_repository import EntryRepository


class EntryService:
    def __init__(self, repository: EntryRepository) -> None:
        self._repository = repository

    def create_entry(self, user_id: str, request: CreateEntryRequest) -> Entry:
        entry = Entry(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_id=str(uuid.uuid4()),
            entry=request.entry,
        )
        self._repository.save(entry)
        return entry

    def get_entry(self, user_id: str, entry_id: str) -> Entry | None:
        return self._repository.get(user_id, entry_id)

    def list_entries(self, user_id: str) -> list[Entry]:
        return self._repository.list_by_user(user_id)