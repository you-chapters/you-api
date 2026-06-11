import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user_id, get_entry_service, get_qa_service
from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
from app.llm.in_memory_llm_client import InMemoryLLMClient
from app.main import app
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
from app.services.entry_service import EntryService
from app.services.qa_service import QaService

USER_ID = "test-user"


@pytest.fixture
def client() -> TestClient:
    service = EntryService(InMemoryEntryRepository())
    app.dependency_overrides[get_entry_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def service_client():
    repo = InMemoryEntryRepository()
    service = EntryService(repo)
    app.dependency_overrides[get_entry_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app), service
    app.dependency_overrides.clear()


@pytest.fixture
def search_client() -> TestClient:
    repo = InMemoryEntryRepository()
    embedding = InMemoryEmbeddingClient()
    vector_repo = InMemoryVectorRepository()
    service = EntryService(repo, embedding, vector_repo)
    app.dependency_overrides[get_entry_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app), service, embedding, vector_repo
    app.dependency_overrides.clear()


def test_create_entry(client: TestClient) -> None:
    response = client.post("/entries", json={"entry": "hello"})

    assert response.status_code == 201
    data = response.json()
    assert data["entry"] == "hello"
    assert data["user_id"] == USER_ID
    assert data["entry_id"]
    assert data["timestamp"]


def test_get_entry(client: TestClient) -> None:
    created = client.post("/entries", json={"entry": "hello"}).json()

    response = client.get(f"/entries/{created['entry_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_entry_not_found(client: TestClient) -> None:
    response = client.get("/entries/nonexistent")

    assert response.status_code == 404


def test_list_entries(client: TestClient) -> None:
    client.post("/entries", json={"entry": "a"})
    client.post("/entries", json={"entry": "b"})

    response = client.get("/entries")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_entries_empty(client: TestClient) -> None:
    response = client.get("/entries")

    assert response.status_code == 200
    assert response.json() == []


def test_create_entry_with_location(client: TestClient) -> None:
    response = client.post("/entries", json={"entry": "hello", "location": "NYC"})

    assert response.status_code == 201
    assert response.json()["location"] == "NYC"


def test_create_entry_location_defaults_to_none(client: TestClient) -> None:
    response = client.post("/entries", json={"entry": "hello"})

    assert response.status_code == 201
    assert response.json()["location"] is None


def test_create_entry_rejects_oversized_entry(client: TestClient) -> None:
    response = client.post("/entries", json={"entry": "x" * 10_001})

    assert response.status_code == 422


def test_search_entries_returns_results(search_client) -> None:
    client, service, embedding, vector_repo = search_client
    created = client.post("/entries", json={"entry": "hello world"}).json()
    vector_repo.upsert(created["entry_id"], USER_ID, embedding.embed("hello world"), 1000)

    response = client.post("/entries/search", json={"query": "hello world"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["entry_id"] == created["entry_id"]


def test_search_entries_returns_empty_when_nothing_indexed(search_client) -> None:
    client, *_ = search_client
    client.post("/entries", json={"entry": "hello"})

    response = client.post("/entries/search", json={"query": "hello"})

    assert response.status_code == 200
    assert response.json()["entries"] == []


def test_search_entries_rejects_oversized_query(search_client) -> None:
    client, *_ = search_client
    response = client.post("/entries/search", json={"query": "q" * 1_001})

    assert response.status_code == 422


def test_list_entries_with_from_date(service_client) -> None:
    from app.models.entry import Entry
    client, service = service_client
    service._repository.save(Entry(user_id=USER_ID, entry_id="e1", entry="a", timestamp="2026-06-01T10:00:00+00:00"))
    service._repository.save(Entry(user_id=USER_ID, entry_id="e2", entry="b", timestamp="2026-06-08T10:00:00+00:00"))

    response = client.get("/entries?from_date=2026-06-02")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_id"] == "e2"


def test_list_entries_with_to_date(service_client) -> None:
    from app.models.entry import Entry
    client, service = service_client
    service._repository.save(Entry(user_id=USER_ID, entry_id="e1", entry="a", timestamp="2026-06-01T10:00:00+00:00"))
    service._repository.save(Entry(user_id=USER_ID, entry_id="e2", entry="b", timestamp="2026-06-08T10:00:00+00:00"))

    response = client.get("/entries?to_date=2026-06-07")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_id"] == "e1"


def test_list_entries_with_date_range(service_client) -> None:
    from app.models.entry import Entry
    client, service = service_client
    service._repository.save(Entry(user_id=USER_ID, entry_id="e1", entry="a", timestamp="2026-06-01T10:00:00+00:00"))
    service._repository.save(Entry(user_id=USER_ID, entry_id="e2", entry="b", timestamp="2026-06-05T10:00:00+00:00"))
    service._repository.save(Entry(user_id=USER_ID, entry_id="e3", entry="c", timestamp="2026-06-10T10:00:00+00:00"))

    response = client.get("/entries?from_date=2026-06-02&to_date=2026-06-08")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_id"] == "e2"


def test_get_summary_empty(client: TestClient) -> None:
    response = client.get("/entries/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["period_days"] == 30
    assert data["entry_count"] == 0
    assert data["mood_timeline"] == []
    assert data["top_topics"] == []
    assert data["top_people"] == []
    assert data["top_locations"] == []


def test_get_summary_period_param(client: TestClient) -> None:
    response = client.get("/entries/summary?period=7")

    assert response.status_code == 200
    assert response.json()["period_days"] == 7


@pytest.fixture
def qa_client():
    repo = InMemoryEntryRepository()
    embedding = InMemoryEmbeddingClient()
    vector_repo = InMemoryVectorRepository()
    entry_service = EntryService(repo, embedding, vector_repo)
    qa_service = QaService(entry_service, InMemoryLLMClient())
    app.dependency_overrides[get_entry_service] = lambda: entry_service
    app.dependency_overrides[get_qa_service] = lambda: qa_service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app), entry_service, embedding, vector_repo
    app.dependency_overrides.clear()


def test_ask_question_returns_answer_and_sources(qa_client) -> None:
    client, entry_service, embedding, vector_repo = qa_client
    created = client.post("/entries", json={"entry": "I went hiking today."}).json()
    vector_repo.upsert(created["entry_id"], USER_ID, embedding.embed("hiking"), 1000)

    response = client.post("/entries/ask", json={"question": "What did I do today?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"]
    assert any(s["entry_id"] == created["entry_id"] for s in data["sources"])


def test_get_on_this_day_returns_entries(service_client) -> None:
    from unittest.mock import patch
    from datetime import datetime, timezone
    from app.models.entry import Entry
    client, service = service_client
    service._repository.save(Entry(user_id=USER_ID, entry_id="e1", entry="a", timestamp="2025-06-11T10:00:00+00:00"))
    service._repository.save(Entry(user_id=USER_ID, entry_id="e2", entry="b", timestamp="2025-07-04T10:00:00+00:00"))
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.services.entry_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        response = client.get("/entries/on-this-day")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_id"] == "e1"


def test_get_on_this_day_returns_empty_list(service_client) -> None:
    from unittest.mock import patch
    from datetime import datetime, timezone
    client, _ = service_client
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.services.entry_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        response = client.get("/entries/on-this-day")

    assert response.status_code == 200
    assert response.json() == []


def test_ask_question_rejects_oversized_question(qa_client) -> None:
    client, *_ = qa_client
    response = client.post("/entries/ask", json={"question": "q" * 1_001})

    assert response.status_code == 422
