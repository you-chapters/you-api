"""
Integration tests for the tagging pipeline.

Exercises the full flow without real AWS/OpenAI:
- HTTP layer: POST /entries with location → entry created, tags=null (async not yet run)
- Embedding handler: DynamoDB stream event → tags extracted → augmented embed → Pinecone upsert → DynamoDB write-back
"""
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

import app.handler_embedding as handler_module
from app.dependencies import get_current_user_id, get_service
from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
from app.main import app
from app.models.entry_tags import EntryTags
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
from app.services.entry_service import EntryService
from app.tag_extraction.in_memory_tag_extraction_client import InMemoryTagExtractionClient

USER_ID = "test-user"

_REALISTIC_TAGS = EntryTags(
    people=["Alice Smith", "Bob Jones"],
    locations=["New York", "Central Park"],
    topics=["work", "relationships"],
    mood="positive",
    time_markers=["last Tuesday", "next month"],
)


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client():
    service = EntryService(InMemoryEntryRepository())
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_entry_with_location_returns_null_tags(http_client) -> None:
    """Tags are null immediately after creation — they're filled in async by the Lambda."""
    response = http_client.post("/entries", json={"entry": "Met Alice in Central Park.", "location": "New York"})

    assert response.status_code == 201
    data = response.json()
    assert data["location"] == "New York"
    assert data["tags"] is None


def test_create_entry_location_is_optional(http_client) -> None:
    response = http_client.post("/entries", json={"entry": "Just a plain entry."})

    assert response.status_code == 201
    assert response.json()["location"] is None
    assert response.json()["tags"] is None


def test_list_entries_includes_location_and_tags_fields(http_client) -> None:
    http_client.post("/entries", json={"entry": "Entry A", "location": "Paris"})
    http_client.post("/entries", json={"entry": "Entry B"})

    response = http_client.get("/entries")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    locations = {e["location"] for e in items}
    assert locations == {"Paris", None}


# ---------------------------------------------------------------------------
# Embedding handler pipeline
# ---------------------------------------------------------------------------

def _make_stream_event(entry_id, user_id, timestamp, entry_text, location=None):
    new_image = {
        "entry_id": {"S": entry_id},
        "user_id": {"S": user_id},
        "timestamp": {"S": timestamp},
        "entry": {"S": entry_text},
    }
    if location:
        new_image["location"] = {"S": location}
    return {"Records": [{"eventName": "INSERT", "dynamodb": {"NewImage": new_image}}]}


def _run_handler(event, tags=None):
    """Run handler with in-memory embedding/vector repo and given tags stub."""
    embedding_client = InMemoryEmbeddingClient()
    vector_repo = InMemoryVectorRepository()
    tag_client = MagicMock()
    tag_client.extract.return_value = tags or EntryTags()
    mock_table = MagicMock()

    with patch.object(handler_module, "_embedding_client", return_value=embedding_client), \
         patch.object(handler_module, "_vector_repository", return_value=vector_repo), \
         patch.object(handler_module, "_tag_extraction_client", return_value=tag_client), \
         patch.object(handler_module, "_dynamodb_table", return_value=mock_table):
        handler_module.handler(event, None)

    return tag_client, vector_repo, mock_table, embedding_client


def test_handler_full_pipeline_extracts_and_writes_tags() -> None:
    """Full pipeline: tags extracted → vector upserted with tags → DynamoDB updated."""
    event = _make_stream_event(
        "entry-abc", "user-1", "2024-06-01T09:00:00+00:00",
        "Met Alice in Central Park with Bob Jones.",
        location="New York",
    )

    tag_client, vector_repo, mock_table, _ = _run_handler(event, tags=_REALISTIC_TAGS)

    # Tag extraction called with correct args
    tag_client.extract.assert_called_once_with(
        "Met Alice in Central Park with Bob Jones.",
        "2024-06-01T09:00:00+00:00",
        "New York",
    )

    # Vector repo has the entry
    results = vector_repo.search("user-1", [0.0] * 1536, top_k=10)
    assert "entry-abc" in results

    # DynamoDB write-back called with extracted tags
    mock_table.update_item.assert_called_once_with(
        Key={"user_id": "user-1", "entry_id": "entry-abc"},
        UpdateExpression="SET tags = :tags",
        ExpressionAttributeValues={":tags": _REALISTIC_TAGS.model_dump()},
    )


def test_handler_augmented_text_contains_all_tag_fields() -> None:
    """Embedding receives text enriched with tags so semantic search benefits."""
    event = _make_stream_event(
        "entry-1", "user-1", "2024-06-01T09:00:00+00:00",
        "Had a great day at work.",
    )
    embedding_client = InMemoryEmbeddingClient()
    embedded_texts = []
    original_embed = embedding_client.embed

    def capturing_embed(text):
        embedded_texts.append(text)
        return original_embed(text)

    embedding_client.embed = capturing_embed

    tag_client = MagicMock()
    tag_client.extract.return_value = _REALISTIC_TAGS
    mock_table = MagicMock()

    with patch.object(handler_module, "_embedding_client", return_value=embedding_client), \
         patch.object(handler_module, "_vector_repository", return_value=InMemoryVectorRepository()), \
         patch.object(handler_module, "_tag_extraction_client", return_value=tag_client), \
         patch.object(handler_module, "_dynamodb_table", return_value=mock_table):
        handler_module.handler(event, None)

    assert len(embedded_texts) == 1
    text = embedded_texts[0]
    assert "Alice Smith" in text
    assert "Bob Jones" in text
    assert "New York" in text
    assert "work" in text
    assert "positive" in text
    assert "2024-06-01T09:00:00+00:00" in text
    assert "Had a great day at work." in text


def test_handler_works_with_no_tags_extracted() -> None:
    """Entry with no recognizable content still completes without error."""
    event = _make_stream_event("entry-2", "user-1", "2024-06-01T09:00:00+00:00", "...")

    tag_client, vector_repo, mock_table, _ = _run_handler(event, tags=EntryTags())

    results = vector_repo.search("user-1", [0.0] * 1536)
    assert "entry-2" in results
    mock_table.update_item.assert_called_once()


def test_handler_processes_batch_of_entries() -> None:
    """Multiple INSERT records in one batch are all processed."""
    events = []
    for i in range(3):
        events.append({
            "eventName": "INSERT",
            "dynamodb": {
                "NewImage": {
                    "entry_id": {"S": f"entry-{i}"},
                    "user_id": {"S": "user-1"},
                    "timestamp": {"S": "2024-06-01T09:00:00+00:00"},
                    "entry": {"S": f"Entry number {i}"},
                }
            },
        })
    batch_event = {"Records": events}

    tag_client, vector_repo, mock_table, _ = _run_handler(batch_event, tags=_REALISTIC_TAGS)

    assert tag_client.extract.call_count == 3
    assert mock_table.update_item.call_count == 3
    for i in range(3):
        assert f"entry-{i}" in vector_repo.search("user-1", [0.0] * 1536, top_k=10)