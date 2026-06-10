from app.llm.llm_client import LLMClient
from app.models.qa import QaResult
from app.services.entry_service import EntryService


class QaService:
    def __init__(self, entry_service: EntryService, llm_client: LLMClient) -> None:
        self._entry_service = entry_service
        self._llm_client = llm_client

    def ask_question(self, user_id: str, question: str) -> QaResult:
        entries = self._entry_service.search_entries(user_id, question)
        answer = self._llm_client.answer_question(entries, question)
        return QaResult(answer=answer, sources=entries)