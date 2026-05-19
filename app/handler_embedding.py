from datetime import datetime, timezone
from functools import lru_cache

from app.embedding.embedding_port import EmbeddingPort
from app.repositories.vector_repository import VectorRepository


@lru_cache
def _embedding_port() -> EmbeddingPort:
    from app.embedding.openai_embedding_client import OpenAIEmbeddingClient
    return OpenAIEmbeddingClient()


@lru_cache
def _vector_repository() -> VectorRepository:
    from app.repositories.pinecone_vector_repository import PineconeVectorRepository
    return PineconeVectorRepository()


def handler(event, context):
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        new_image = record["dynamodb"]["NewImage"]
        entry_id = new_image["entry_id"]["S"]
        user_id = new_image["user_id"]["S"]
        timestamp = new_image["timestamp"]["S"]
        entry_text = new_image["entry"]["S"]

        timestamp_unix = int(datetime.fromisoformat(timestamp).astimezone(timezone.utc).timestamp())

        text = f"Date: {timestamp}\n\n{entry_text}"
        vector = _embedding_port().embed(text)
        _vector_repository().upsert(entry_id, user_id, vector, timestamp_unix)
