import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user_id, get_phase_service
from app.main import app
from app.models.phase import PhaseRecord

USER_ID = "test-user"
NOW = datetime.now(timezone.utc).isoformat()


def _phase(phase_id: str | None = None, is_open: bool = True, end_date: str | None = None) -> PhaseRecord:
    return PhaseRecord(
        phase_id=phase_id or str(uuid.uuid4()),
        title="Test Phase",
        description="A test phase description.",
        start_date="2026-01-01",
        end_date=end_date,
        entry_count=5,
        dominant_topics=["work"],
        mean_mood=0.5,
        top_people=["Alice"],
        top_locations=["Home"],
        generated_at=NOW,
        is_open=is_open,
    )


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_service: MagicMock) -> TestClient:
    app.dependency_overrides[get_phase_service] = lambda: mock_service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_phases_returns_list(client: TestClient, mock_service: MagicMock) -> None:
    p1 = _phase(is_open=False, end_date="2026-02-01")
    p2 = _phase(is_open=True)
    mock_service.get_phases.return_value = [p1, p2]

    response = client.get("/phases")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    mock_service.get_phases.assert_called_once_with(USER_ID, refresh=False)


def test_get_phases_empty(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.get_phases.return_value = []

    response = client.get("/phases")

    assert response.status_code == 200
    assert response.json() == []


def test_get_phases_refresh_param(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.get_phases.return_value = []

    client.get("/phases?refresh=true")

    mock_service.get_phases.assert_called_once_with(USER_ID, refresh=True)


def test_get_phases_response_shape(client: TestClient, mock_service: MagicMock) -> None:
    p = _phase()
    mock_service.get_phases.return_value = [p]

    data = client.get("/phases").json()[0]

    assert "phase_id" in data
    assert "title" in data
    assert "description" in data
    assert "start_date" in data
    assert "entry_count" in data
    assert "is_open" in data


def test_get_current_phase_returns_open(client: TestClient, mock_service: MagicMock) -> None:
    p = _phase(is_open=True)
    mock_service.get_current_phase.return_value = p

    response = client.get("/phases/current")

    assert response.status_code == 200
    assert response.json()["is_open"] is True
    mock_service.get_current_phase.assert_called_once_with(USER_ID)


def test_get_current_phase_none_returns_null(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.get_current_phase.return_value = None

    response = client.get("/phases/current")

    assert response.status_code == 200
    assert response.json() is None


def test_get_phase_by_id_found(client: TestClient, mock_service: MagicMock) -> None:
    pid = str(uuid.uuid4())
    p = _phase(phase_id=pid)
    mock_service.get_phase.return_value = p

    response = client.get(f"/phases/{pid}")

    assert response.status_code == 200
    assert response.json()["phase_id"] == pid
    mock_service.get_phase.assert_called_once_with(USER_ID, pid)


def test_get_phase_by_id_not_found(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.get_phase.return_value = None

    response = client.get("/phases/nonexistent-id")

    assert response.status_code == 404


def test_current_route_not_captured_as_phase_id(client: TestClient, mock_service: MagicMock) -> None:
    mock_service.get_current_phase.return_value = None

    # /phases/current must NOT route to get_phase("current")
    response = client.get("/phases/current")

    mock_service.get_current_phase.assert_called_once()
    mock_service.get_phase.assert_not_called()
    assert response.status_code == 200
