import pytest

from app.models.entry import CreateEntryRequest
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.services.entry_service import EntryService


@pytest.fixture
def service() -> EntryService:
    return EntryService(InMemoryEntryRepository())


def test_create_entry_returns_entry_with_correct_fields(service: EntryService) -> None:
    entry = service.create_entry("user-1", CreateEntryRequest(entry="hello"))

    assert entry.user_id == "user-1"
    assert entry.entry == "hello"
    assert entry.entry_id
    assert entry.timestamp


def test_get_entry_returns_created_entry(service: EntryService) -> None:
    created = service.create_entry("user-1", CreateEntryRequest(entry="hello"))

    fetched = service.get_entry("user-1", created.entry_id)

    assert fetched == created


def test_get_entry_returns_none_for_wrong_user(service: EntryService) -> None:
    created = service.create_entry("user-1", CreateEntryRequest(entry="hello"))

    assert service.get_entry("user-2", created.entry_id) is None


def test_get_entry_returns_none_for_missing_id(service: EntryService) -> None:
    assert service.get_entry("user-1", "nonexistent") is None


def test_list_entries_returns_only_user_entries(service: EntryService) -> None:
    service.create_entry("user-1", CreateEntryRequest(entry="a"))
    service.create_entry("user-1", CreateEntryRequest(entry="b"))
    service.create_entry("user-2", CreateEntryRequest(entry="c"))

    entries = service.list_entries("user-1")

    assert len(entries) == 2
    assert all(e.user_id == "user-1" for e in entries)


def test_list_entries_returns_empty_for_unknown_user(service: EntryService) -> None:
    assert service.list_entries("unknown") == []
