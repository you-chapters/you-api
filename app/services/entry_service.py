import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.embedding.embedding_port import EmbeddingPort
from app.models.entry import CreateEntryRequest, Entry
from app.models.summary import MoodPoint, PersonCount, PeriodSummary, TopicCount
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
        entries = self._repository.list_by_user(user_id)
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def get_summary(self, user_id: str, period_days: int = 30) -> PeriodSummary:
        all_entries = self._repository.list_by_user(user_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()
        entries = [e for e in all_entries if e.timestamp >= cutoff]

        topic_counter: Counter[str] = Counter()
        person_counter: Counter[str] = Counter()
        mood_by_date: dict[str, str] = {}

        for entry in sorted(entries, key=lambda e: e.timestamp):
            if entry.tags is None:
                continue
            topic_counter.update(entry.tags.topics)
            person_counter.update(entry.tags.people)
            if entry.tags.mood:
                mood_by_date[entry.timestamp[:10]] = entry.tags.mood

        return PeriodSummary(
            period_days=period_days,
            entry_count=len(entries),
            mood_timeline=[MoodPoint(date=d, mood=m) for d, m in sorted(mood_by_date.items())],
            top_topics=[TopicCount(topic=t, count=c) for t, c in topic_counter.most_common()],
            top_people=[PersonCount(name=n, count=c) for n, c in person_counter.most_common()],
        )

    def search_entries(self, user_id: str, query: str) -> list[Entry]:
        if not self._embedding_port or not self._vector_repository:
            raise RuntimeError("Search not configured")
        vector = self._embedding_port.embed(query)
        entry_ids = self._vector_repository.search(user_id, vector)
        return self._repository.get_many(user_id, entry_ids)
