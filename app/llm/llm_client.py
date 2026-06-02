from abc import ABC, abstractmethod

from app.models.entry import Entry


class LLMClient(ABC):
    @abstractmethod
    def generate_narrative(self, entries: list[Entry], period_label: str) -> str: ...

    @abstractmethod
    def generate_phase(self, entries: list[Entry], signals_summary: str, hint: str) -> tuple[str, str]: ...
