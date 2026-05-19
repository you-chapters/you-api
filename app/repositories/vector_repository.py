from abc import ABC, abstractmethod


class VectorRepository(ABC):
    @abstractmethod
    def upsert(self, entry_id: str, user_id: str, vector: list[float], timestamp: int) -> None: ...

    @abstractmethod
    def search(self, user_id: str, vector: list[float], top_k: int = 10) -> list[str]: ...
