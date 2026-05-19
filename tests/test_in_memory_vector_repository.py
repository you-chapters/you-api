import pytest

from app.repositories.in_memory_vector_repository import InMemoryVectorRepository

_DIMS = 4


def _vec(seed: float) -> list[float]:
    return [seed, seed, seed, seed]


@pytest.fixture
def repo() -> InMemoryVectorRepository:
    return InMemoryVectorRepository()


def test_search_returns_empty_when_store_is_empty(repo: InMemoryVectorRepository) -> None:
    assert repo.search("user-1", _vec(0.5)) == []


def test_upsert_and_search_returns_entry_id(repo: InMemoryVectorRepository) -> None:
    repo.upsert("entry-1", "user-1", _vec(1.0), 1000)
    result = repo.search("user-1", _vec(1.0))
    assert result == ["entry-1"]


def test_search_filters_by_user_id(repo: InMemoryVectorRepository) -> None:
    repo.upsert("entry-1", "user-1", _vec(1.0), 1000)
    repo.upsert("entry-2", "user-2", _vec(1.0), 1000)

    assert repo.search("user-1", _vec(1.0)) == ["entry-1"]
    assert repo.search("user-2", _vec(1.0)) == ["entry-2"]


def test_search_respects_top_k(repo: InMemoryVectorRepository) -> None:
    for i in range(5):
        repo.upsert(f"entry-{i}", "user-1", _vec(float(i)), 1000)

    result = repo.search("user-1", _vec(4.0), top_k=2)
    assert len(result) == 2


def test_search_returns_closest_vector_first(repo: InMemoryVectorRepository) -> None:
    repo.upsert("far", "user-1", [1.0, 0.0, 0.0, 0.0], 1000)
    repo.upsert("close", "user-1", [0.9, 0.9, 0.9, 0.9], 1000)

    result = repo.search("user-1", [1.0, 1.0, 1.0, 1.0])
    assert result[0] == "close"


def test_upsert_overwrites_existing_entry(repo: InMemoryVectorRepository) -> None:
    repo.upsert("entry-1", "user-1", _vec(0.1), 1000)
    repo.upsert("entry-1", "user-1", _vec(1.0), 2000)

    result = repo.search("user-1", _vec(1.0))
    assert result == ["entry-1"]
    assert len(result) == 1


def test_search_returns_empty_for_unknown_user(repo: InMemoryVectorRepository) -> None:
    repo.upsert("entry-1", "user-1", _vec(1.0), 1000)
    assert repo.search("unknown", _vec(1.0)) == []