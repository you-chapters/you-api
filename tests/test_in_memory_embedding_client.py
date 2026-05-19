from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient

_DIMS = 1536


def test_embed_returns_correct_dimensions() -> None:
    client = InMemoryEmbeddingClient()
    result = client.embed("hello world")
    assert len(result) == _DIMS


def test_embed_all_values_are_floats() -> None:
    client = InMemoryEmbeddingClient()
    result = client.embed("test")
    assert all(isinstance(v, float) for v in result)


def test_embed_values_in_range() -> None:
    client = InMemoryEmbeddingClient()
    result = client.embed("some text")
    assert all(-1.0 <= v <= 1.0 for v in result)


def test_embed_is_deterministic() -> None:
    client = InMemoryEmbeddingClient()
    assert client.embed("same text") == client.embed("same text")


def test_embed_different_texts_produce_different_vectors() -> None:
    client = InMemoryEmbeddingClient()
    assert client.embed("text one") != client.embed("text two")