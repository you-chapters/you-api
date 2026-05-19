import hashlib

from app.ports.embedding_port import EmbeddingPort

_DIMS = 1536


class InMemoryEmbeddingClient(EmbeddingPort):
    def embed(self, text: str) -> list[float]:
        h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        result = []
        for _ in range(_DIMS):
            h = (h * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            result.append((h / (1 << 64)) * 2 - 1)
        return result
