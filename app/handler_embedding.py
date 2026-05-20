import os
from datetime import datetime, timezone
from functools import lru_cache

from app.embedding.embedding_port import EmbeddingPort
from app.repositories.vector_repository import VectorRepository
from app.tag_extraction.tag_extraction_port import TagExtractionClient


@lru_cache
def _embedding_port() -> EmbeddingPort:
    from app.embedding.openai_embedding_client import OpenAIEmbeddingClient
    return OpenAIEmbeddingClient()


@lru_cache
def _vector_repository() -> VectorRepository:
    from app.repositories.pinecone_vector_repository import PineconeVectorRepository
    return PineconeVectorRepository()


@lru_cache
def _tag_extraction_client() -> TagExtractionClient:
    if os.environ.get("TAG_EXTRACTION_TYPE", "openai") == "openai":
        from app.tag_extraction.openai_tag_extraction_client import OpenAITagExtractionClient
        return OpenAITagExtractionClient()
    from app.tag_extraction.in_memory_tag_extraction_client import InMemoryTagExtractionClient
    return InMemoryTagExtractionClient()


@lru_cache
def _dynamodb_table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE_NAME"])


def handler(event, context):
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        new_image = record["dynamodb"]["NewImage"]
        entry_id = new_image["entry_id"]["S"]
        user_id = new_image["user_id"]["S"]
        timestamp = new_image["timestamp"]["S"]
        entry_text = new_image["entry"]["S"]
        user_location = new_image.get("location", {}).get("S")

        timestamp_unix = int(datetime.fromisoformat(timestamp).astimezone(timezone.utc).timestamp())

        tags = _tag_extraction_client().extract(entry_text, timestamp, user_location)

        augmented_text = (
            f"Date: {timestamp}\n"
            f"Topics: {', '.join(tags.topics) or 'none'}\n"
            f"People: {', '.join(tags.people) or 'none'}\n"
            f"Mood: {tags.mood or 'unknown'}\n"
            f"Location: {', '.join(tags.locations) or user_location or 'unknown'}\n\n"
            f"{entry_text}"
        )

        vector = _embedding_port().embed(augmented_text)
        _vector_repository().upsert(entry_id, user_id, vector, timestamp_unix, tags)

        _dynamodb_table().update_item(
            Key={"user_id": user_id, "entry_id": entry_id},
            UpdateExpression="SET tags = :tags",
            ExpressionAttributeValues={":tags": tags.model_dump()},
        )
