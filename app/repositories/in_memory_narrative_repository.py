from app.models.narrative import NarrativeSummary
from app.models.phase import PhaseIndex, PhaseRecord
from app.repositories.narrative_repository import NarrativeRepository


class InMemoryNarrativeRepository(NarrativeRepository):
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], NarrativeSummary] = {}
        self._phases: dict[tuple[str, str], PhaseRecord] = {}
        self._phase_indexes: dict[str, PhaseIndex] = {}

    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None:
        return self._store.get((user_id, record_id))

    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None:
        self._store[(user_id, record_id)] = summary

    def get_phase(self, user_id: str, phase_id: str) -> PhaseRecord | None:
        return self._phases.get((user_id, phase_id))

    def save_phase(self, user_id: str, phase_id: str, record: PhaseRecord) -> None:
        self._phases[(user_id, phase_id)] = record

    def batch_get_phases(self, user_id: str, phase_ids: list[str]) -> list[PhaseRecord]:
        records = [
            self._phases[k]
            for k in [(user_id, pid) for pid in phase_ids]
            if k in self._phases
        ]
        records.sort(key=lambda r: r.start_date)
        return records

    def get_phase_index(self, user_id: str) -> PhaseIndex | None:
        return self._phase_indexes.get(user_id)

    def save_phase_index(self, user_id: str, index: PhaseIndex) -> None:
        self._phase_indexes[user_id] = index
