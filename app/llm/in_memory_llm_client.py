from app.llm.llm_client import LLMClient
from app.models.entry import Entry


class InMemoryLLMClient(LLMClient):
    def generate_narrative(self, entries: list[Entry], period_label: str) -> str:
        return f"Stub narrative for {period_label} ({len(entries)} entries)."

    def generate_phase(self, entries: list[Entry], signals_summary: str, hint: str) -> tuple[str, str]:
        return (f"Stub Phase ({len(entries)} entries)", f"Stub description. {hint}")
