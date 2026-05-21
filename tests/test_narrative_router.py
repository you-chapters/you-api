from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user_id, get_narrative_service
from app.main import app
from app.models.narrative import NarrativeSummary
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_narrative_repository import InMemoryNarrativeRepository
from app.llm.in_memory_llm_client import InMemoryLLMClient
from app.services.narrative_service import NarrativeService

USER_ID = "test-user"
TODAY = datetime.now(timezone.utc).date()
CURRENT_WEEK = TODAY.strftime("%G-W%V")
CURRENT_MONTH = TODAY.strftime("%Y-%m")


def _make_narrative_service():
    return NarrativeService(
        InMemoryEntryRepository(),
        InMemoryNarrativeRepository(),
        InMemoryLLMClient(),
    )


@pytest.fixture
def client() -> TestClient:
    svc = _make_narrative_service()
    app.dependency_overrides[get_narrative_service] = lambda: svc
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_narrative_default_returns_current_week(client: TestClient) -> None:
    response = client.get("/entries/narrative")

    assert response.status_code == 200
    data = response.json()
    assert data["period_type"] == "week"
    assert data["period_key"] == CURRENT_WEEK
    assert data["is_cached"] is False
    assert "text" in data
    assert "generated_at" in data


def test_narrative_second_call_is_cached(client: TestClient) -> None:
    client.get("/entries/narrative")
    response = client.get("/entries/narrative")

    assert response.status_code == 200
    assert response.json()["is_cached"] is True


def test_narrative_force_refresh(client: TestClient) -> None:
    first = client.get("/entries/narrative").json()
    response = client.get("/entries/narrative?refresh=true")

    assert response.status_code == 200
    data = response.json()
    assert data["is_cached"] is False
    assert data["generated_at"] >= first["generated_at"]


def test_narrative_type_month(client: TestClient) -> None:
    response = client.get("/entries/narrative?type=month")

    assert response.status_code == 200
    data = response.json()
    assert data["period_type"] == "month"
    assert data["period_key"] == CURRENT_MONTH


def test_narrative_explicit_past_week_key(client: TestClient) -> None:
    response = client.get("/entries/narrative?type=week&key=2025-W01")

    assert response.status_code == 200
    data = response.json()
    assert data["period_key"] == "2025-W01"


def test_narrative_invalid_type_returns_422(client: TestClient) -> None:
    response = client.get("/entries/narrative?type=invalid")

    assert response.status_code == 422


def test_narrative_entry_count_in_response(client: TestClient) -> None:
    response = client.get("/entries/narrative")

    assert response.status_code == 200
    assert response.json()["entry_count"] == 0
