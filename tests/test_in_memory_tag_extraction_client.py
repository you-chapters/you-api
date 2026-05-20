from app.models.entry_tags import EntryTags
from app.tag_extraction.in_memory_tag_extraction_client import InMemoryTagExtractionClient


def test_extract_returns_empty_tags() -> None:
    client = InMemoryTagExtractionClient()
    result = client.extract("Some journal text", "2024-01-15T10:00:00+00:00", None)

    assert result == EntryTags()


def test_extract_ignores_location() -> None:
    client = InMemoryTagExtractionClient()
    result = client.extract("Some journal text", "2024-01-15T10:00:00+00:00", "New York")

    assert result.locations == []


def test_extract_returns_empty_lists_and_none_mood() -> None:
    client = InMemoryTagExtractionClient()
    result = client.extract("text", "2024-01-15T10:00:00+00:00", None)

    assert result.people == []
    assert result.topics == []
    assert result.mood is None
    assert result.time_markers == []
