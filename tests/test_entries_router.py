import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user_id, get_service
from app.main import app
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.services.entry_service import EntryService

USER_ID = "test-user"


@pytest.fixture
def client() -> TestClient:
    service = EntryService(InMemoryEntryRepository())
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app)
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


def test_create_entry_rejects_oversized_entry(client: TestClient) -> None:
    response = client.post("/entries", json={"entry": "x" * 10_001})

    assert response.status_code == 422
