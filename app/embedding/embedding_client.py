from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...
