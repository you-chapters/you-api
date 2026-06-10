import pytest

from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
from app.llm.in_memory_llm_client import InMemoryLLMClient
from app.models.entry import CreateEntryRequest
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
from app.services.entry_service import EntryService
from app.services.qa_service import QaService


@pytest.fixture
def services():
    repo = InMemoryEntryRepository()
    embedding = InMemoryEmbeddingClient()
    vector_repo = InMemoryVectorRepository()
    entry_service = EntryService(repo, embedding, vector_repo)
    qa_service = QaService(entry_service, InMemoryLLMClient())
    return entry_service, qa_service, embedding, vector_repo


def test_ask_question_returns_answer_and_source_ids(services) -> None:
    entry_service, qa_service, embedding, vector_repo = services
    entry = entry_service.create_entry("user-1", CreateEntryRequest(entry="I went hiking today."))
    vector_repo.upsert(entry.entry_id, "user-1", embedding.embed("hiking"), 1000)

    result = qa_service.ask_question("user-1", "What did I do today?")

    assert result.answer
    assert entry.entry_id in result.sources


def test_ask_question_returns_empty_sources_when_nothing_indexed(services) -> None:
    entry_service, qa_service, *_ = services
    entry_service.create_entry("user-1", CreateEntryRequest(entry="hello"))

    result = qa_service.ask_question("user-1", "anything?")

    assert result.sources == []


def test_ask_question_respects_user_isolation(services) -> None:
    entry_service, qa_service, embedding, vector_repo = services
    e1 = entry_service.create_entry("user-1", CreateEntryRequest(entry="user one entry"))
    e2 = entry_service.create_entry("user-2", CreateEntryRequest(entry="user two entry"))
    vector_repo.upsert(e1.entry_id, "user-1", embedding.embed("entry"), 1000)
    vector_repo.upsert(e2.entry_id, "user-2", embedding.embed("entry"), 1000)

    result = qa_service.ask_question("user-1", "what did I write?")

    assert e1.entry_id in result.sources
    assert e2.entry_id not in result.sources
