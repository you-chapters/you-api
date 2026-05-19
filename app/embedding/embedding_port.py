from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...
