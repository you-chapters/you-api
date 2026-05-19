from unittest.mock import patch

import pytest

from app.embedding.openai_embedding_client import OpenAIEmbeddingClient


@pytest.fixture
def mock_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("app.embedding.openai_embedding_client.OpenAI") as m:
        yield m.return_value


@pytest.fixture
def client(mock_openai) -> OpenAIEmbeddingClient:
    return OpenAIEmbeddingClient()


def test_embed_returns_vector(client, mock_openai) -> None:
    expected = [0.1, 0.2, 0.3]
    mock_openai.embeddings.create.return_value.data[0].embedding = expected

    assert client.embed("hello") == expected


def test_embed_calls_correct_model(client, mock_openai) -> None:
    mock_openai.embeddings.create.return_value.data[0].embedding = [0.1]

    client.embed("test text")

    mock_openai.embeddings.create.assert_called_once_with(model="text-embedding-3-small", input="test text")