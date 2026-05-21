import pytest

from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
from app.models.entry import CreateEntryRequest, Entry
from app.models.entry_tags import EntryTags
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
from app.services.entry_service import EntryService


@pytest.fixture
def service() -> EntryService:
    return EntryService(InMemoryEntryRepository())


@pytest.fixture
def search_service() -> EntryService:
    return EntryService(InMemoryEntryRepository(), InMemoryEmbeddingClient(), InMemoryVectorRepository())


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


def test_list_entries_returns_latest_first(service: EntryService) -> None:
    e1 = service.create_entry("user-1", CreateEntryRequest(entry="first"))
    e2 = service.create_entry("user-1", CreateEntryRequest(entry="second"))
    e3 = service.create_entry("user-1", CreateEntryRequest(entry="third"))

    entries = service.list_entries("user-1")

    assert entries[0].entry_id == e3.entry_id
    assert entries[1].entry_id == e2.entry_id
    assert entries[2].entry_id == e1.entry_id


def test_search_entries_raises_when_not_configured(service: EntryService) -> None:
    with pytest.raises(RuntimeError, match="Search not configured"):
        service.search_entries("user-1", "anything")


def test_search_entries_returns_matching_entries(search_service: EntryService) -> None:
    entry = search_service.create_entry("user-1", CreateEntryRequest(entry="hello"))
    search_service._vector_repository.upsert(entry.entry_id, "user-1", search_service._embedding_client.embed("hello"), 1000)

    results = search_service.search_entries("user-1", "hello")

    assert len(results) == 1
    assert results[0].entry_id == entry.entry_id


def test_search_entries_returns_empty_when_vector_store_empty(search_service: EntryService) -> None:
    search_service.create_entry("user-1", CreateEntryRequest(entry="hello"))

    results = search_service.search_entries("user-1", "hello")

    assert results == []


def test_search_entries_respects_user_isolation(search_service: EntryService) -> None:
    e1 = search_service.create_entry("user-1", CreateEntryRequest(entry="hello"))
    e2 = search_service.create_entry("user-2", CreateEntryRequest(entry="hello"))
    search_service._vector_repository.upsert(e1.entry_id, "user-1", search_service._embedding_client.embed("hello"), 1000)
    search_service._vector_repository.upsert(e2.entry_id, "user-2", search_service._embedding_client.embed("hello"), 1000)

    results = search_service.search_entries("user-1", "hello")

    assert all(r.user_id == "user-1" for r in results)


def test_get_summary_empty(service: EntryService) -> None:
    summary = service.get_summary("user-1")

    assert summary.period_days == 30
    assert summary.entry_count == 0
    assert summary.mood_timeline == []
    assert summary.top_topics == []
    assert summary.top_people == []


def test_get_summary_counts_entries_in_period(service: EntryService) -> None:
    service._repository.save(Entry(
        user_id="user-1", entry_id="e1", entry="a",
        timestamp="2026-05-19T10:00:00+00:00",
        tags=EntryTags(topics=["work"], people=["Alice"], mood="positive"),
    ))
    service._repository.save(Entry(
        user_id="user-1", entry_id="e2", entry="b",
        timestamp="2020-01-01T00:00:00+00:00",
        tags=EntryTags(topics=["health"]),
    ))

    summary = service.get_summary("user-1", period_days=30)

    assert summary.entry_count == 1


def test_get_summary_aggregates_topics_and_people(service: EntryService) -> None:
    service._repository.save(Entry(
        user_id="user-1", entry_id="e1", entry="a",
        timestamp="2026-05-18T10:00:00+00:00",
        tags=EntryTags(topics=["work", "health"], people=["Alice"]),
    ))
    service._repository.save(Entry(
        user_id="user-1", entry_id="e2", entry="b",
        timestamp="2026-05-19T10:00:00+00:00",
        tags=EntryTags(topics=["work"], people=["Alice", "Bob"]),
    ))

    summary = service.get_summary("user-1", period_days=30)

    topics = {t.topic: t.count for t in summary.top_topics}
    assert topics == {"work": 2, "health": 1}
    people = {p.name: p.count for p in summary.top_people}
    assert people == {"Alice": 2, "Bob": 1}


def test_get_summary_mood_timeline_latest_entry_wins(service: EntryService) -> None:
    service._repository.save(Entry(
        user_id="user-1", entry_id="e1", entry="a",
        timestamp="2026-05-19T08:00:00+00:00",
        tags=EntryTags(mood="negative"),
    ))
    service._repository.save(Entry(
        user_id="user-1", entry_id="e2", entry="b",
        timestamp="2026-05-19T20:00:00+00:00",
        tags=EntryTags(mood="positive"),
    ))

    summary = service.get_summary("user-1", period_days=30)

    assert len(summary.mood_timeline) == 1
    assert summary.mood_timeline[0].date == "2026-05-19"
    assert summary.mood_timeline[0].mood == "positive"


def test_get_summary_skips_entries_without_tags(service: EntryService) -> None:
    service._repository.save(Entry(
        user_id="user-1", entry_id="e1", entry="a",
        timestamp="2026-05-19T10:00:00+00:00",
        tags=None,
    ))

    summary = service.get_summary("user-1", period_days=30)

    assert summary.entry_count == 1
    assert summary.mood_timeline == []
    assert summary.top_topics == []


def test_get_summary_isolates_by_user(service: EntryService) -> None:
    service._repository.save(Entry(
        user_id="user-1", entry_id="e1", entry="a",
        timestamp="2026-05-19T10:00:00+00:00",
        tags=EntryTags(topics=["work"]),
    ))
    service._repository.save(Entry(
        user_id="user-2", entry_id="e2", entry="b",
        timestamp="2026-05-19T10:00:00+00:00",
        tags=EntryTags(topics=["health"]),
    ))

    summary = service.get_summary("user-1", period_days=30)

    assert summary.entry_count == 1
    assert summary.top_topics[0].topic == "work"
