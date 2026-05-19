from pinecone import Pinecone

from app.config import get_secret
from app.repositories.vector_repository import VectorRepository


class PineconeVectorRepository(VectorRepository):
    def __init__(self) -> None:
        pc = Pinecone(api_key=get_secret("PINECONE_API_KEY"))
        self._index = pc.Index(host=get_secret("PINECONE_INDEX_HOST"))

    def upsert(self, entry_id: str, user_id: str, vector: list[float], timestamp: int) -> None:
        self._index.upsert(vectors=[{"id": entry_id, "values": vector, "metadata": {"user_id": user_id, "timestamp": timestamp}}])

    def search(self, user_id: str, vector: list[float], top_k: int = 10) -> list[str]:
        results = self._index.query(
            vector=vector,
            top_k=top_k,
            filter={"user_id": {"$eq": user_id}},
            include_values=False,
        )
        return [match.id for match in results.matches]
