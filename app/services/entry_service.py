import uuid
from datetime import datetime, timezone

from app.models.entry import CreateEntryRequest, Entry
from app.embedding.embedding_port import EmbeddingPort
from app.repositories.entry_repository import EntryRepository
from app.repositories.vector_repository import VectorRepository


class EntryService:
    def __init__(
            self,
            repository: EntryRepository,
            embedding_port: EmbeddingPort | None = None,
            vector_repository: VectorRepository | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_port = embedding_port
        self._vector_repository = vector_repository

    def create_entry(self, user_id: str, request: CreateEntryRequest) -> Entry:
        entry = Entry(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_id=str(uuid.uuid4()),
            entry=request.entry,
            location=request.location,
        )
        self._repository.save(entry)
        return entry

    def get_entry(self, user_id: str, entry_id: str) -> Entry | None:
        return self._repository.get(user_id, entry_id)

    def list_entries(self, user_id: str) -> list[Entry]:
        return self._repository.list_by_user(user_id)

    def search_entries(self, user_id: str, query: str) -> list[Entry]:
        if not self._embedding_port or not self._vector_repository:
            raise RuntimeError("Search not configured")
        vector = self._embedding_port.embed(query)
        entry_ids = self._vector_repository.search(user_id, vector)
        return self._repository.get_many(user_id, entry_ids)
