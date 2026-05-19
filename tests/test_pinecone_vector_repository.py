from unittest.mock import MagicMock, patch

import pytest

from app.repositories.pinecone_vector_repository import PineconeVectorRepository


@pytest.fixture
def mock_index(monkeypatch):
    monkeypatch.setenv("PINECONE_API_KEY", "test-key")
    monkeypatch.setenv("PINECONE_INDEX_HOST", "test-host")
    with patch("app.repositories.pinecone_vector_repository.Pinecone") as m:
        yield m.return_value.Index.return_value


@pytest.fixture
def repo(mock_index) -> PineconeVectorRepository:
    return PineconeVectorRepository()


def test_upsert_calls_index_upsert(repo, mock_index) -> None:
    repo.upsert("entry-1", "user-1", [0.1, 0.2], 1000)

    mock_index.upsert.assert_called_once_with(
        vectors=[{"id": "entry-1", "values": [0.1, 0.2], "metadata": {"user_id": "user-1", "timestamp": 1000}}]
    )


def test_search_returns_match_ids(repo, mock_index) -> None:
    match1, match2 = MagicMock(id="entry-1"), MagicMock(id="entry-2")
    mock_index.query.return_value.matches = [match1, match2]

    result = repo.search("user-1", [0.1, 0.2], top_k=5)

    assert result == ["entry-1", "entry-2"]
    mock_index.query.assert_called_once_with(
        vector=[0.1, 0.2],
        top_k=5,
        filter={"user_id": {"$eq": "user-1"}},
        include_values=False,
    )


def test_search_returns_empty_when_no_matches(repo, mock_index) -> None:
    mock_index.query.return_value.matches = []

    assert repo.search("user-1", [0.1, 0.2]) == []