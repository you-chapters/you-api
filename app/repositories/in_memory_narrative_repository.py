from app.models.narrative import NarrativeSummary
from app.repositories.narrative_repository import NarrativeRepository


class InMemoryNarrativeRepository(NarrativeRepository):
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], NarrativeSummary] = {}

    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None:
        return self._store.get((user_id, record_id))

    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None:
        self._store[(user_id, record_id)] = summary
