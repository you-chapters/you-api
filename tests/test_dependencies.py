from unittest.mock import MagicMock, patch

import pytest

import app.dependencies as deps
from app.dependencies import get_current_user_id, get_service
from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
from app.services.entry_service import EntryService


@pytest.fixture(autouse=True)
def clear_caches():
    deps._repository.cache_clear()
    deps._embedding_port.cache_clear()
    deps._vector_repository.cache_clear()
    yield
    deps._repository.cache_clear()
    deps._embedding_port.cache_clear()
    deps._vector_repository.cache_clear()


def test_repository_returns_in_memory_by_default(monkeypatch) -> None:
    monkeypatch.delenv("REPOSITORY_TYPE", raising=False)

    assert isinstance(deps._repository(), InMemoryEntryRepository)


def test_repository_returns_dynamodb_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("REPOSITORY_TYPE", "dynamodb")
    monkeypatch.setenv("DYNAMODB_TABLE_NAME", "test-table")

    with patch("app.repositories.dynamodb_entry_repository.boto3.resource"):
        from app.repositories.dynamodb_entry_repository import DynamoDBEntryRepository
        assert isinstance(deps._repository(), DynamoDBEntryRepository)


def test_embedding_port_returns_in_memory_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_TYPE", raising=False)

    assert isinstance(deps._embedding_port(), InMemoryEmbeddingClient)


def test_embedding_port_returns_openai_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_TYPE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("app.embedding.openai_embedding_client.OpenAI"):
        from app.embedding.openai_embedding_client import OpenAIEmbeddingClient
        assert isinstance(deps._embedding_port(), OpenAIEmbeddingClient)


def test_vector_repository_returns_in_memory_by_default(monkeypatch) -> None:
    monkeypatch.delenv("VECTOR_REPOSITORY_TYPE", raising=False)

    assert isinstance(deps._vector_repository(), InMemoryVectorRepository)


def test_vector_repository_returns_pinecone_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("VECTOR_REPOSITORY_TYPE", "pinecone")
    monkeypatch.setenv("PINECONE_API_KEY", "test-key")
    monkeypatch.setenv("PINECONE_INDEX_HOST", "test-host")

    with patch("app.repositories.pinecone_vector_repository.Pinecone"):
        from app.repositories.pinecone_vector_repository import PineconeVectorRepository
        assert isinstance(deps._vector_repository(), PineconeVectorRepository)


def test_get_service_returns_entry_service() -> None:
    assert isinstance(get_service(), EntryService)


def test_get_current_user_id_extracts_sub_from_aws_event() -> None:
    request = MagicMock()
    request.scope = {"aws.event": {"requestContext": {"authorizer": {"claims": {"sub": "user-123"}}}}}

    assert get_current_user_id(request) == "user-123"


def test_get_current_user_id_falls_back_to_dev_user_id_env(monkeypatch) -> None:
    monkeypatch.setenv("DEV_USER_ID", "dev-123")
    request = MagicMock()
    request.scope = {}

    assert get_current_user_id(request) == "dev-123"


def test_get_current_user_id_defaults_to_dev_user(monkeypatch) -> None:
    monkeypatch.delenv("DEV_USER_ID", raising=False)
    request = MagicMock()
    request.scope = {}

    assert get_current_user_id(request) == "dev-user"