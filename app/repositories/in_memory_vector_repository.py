import math

from app.models.entry_tags import EntryTags
from app.repositories.vector_repository import VectorRepository


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / mag if mag else 0.0


class InMemoryVectorRepository(VectorRepository):
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, int, list[float]]] = {}

    def upsert(self, entry_id: str, user_id: str, vector: list[float], timestamp: int, tags: EntryTags | None = None) -> None:
        self._store[entry_id] = (user_id, timestamp, vector)

    def search(self, user_id: str, vector: list[float], top_k: int = 10) -> list[str]:
        candidates = [(eid, v) for eid, (uid, _ts, v) in self._store.items() if uid == user_id]
        scored = sorted(candidates, key=lambda x: _cosine(vector, x[1]), reverse=True)
        return [eid for eid, _ in scored[:top_k]]
