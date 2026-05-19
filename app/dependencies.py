import os
from functools import lru_cache

from fastapi import Request

from app.embedding.embedding_port import EmbeddingPort
from app.repositories.entry_repository import EntryRepository
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.vector_repository import VectorRepository
from app.services.entry_service import EntryService


@lru_cache
def _repository() -> EntryRepository:
    print(f"REPOSITORY_TYPE={os.getenv('REPOSITORY_TYPE')}")
    print(f"DYNAMODB_TABLE_NAME={os.getenv('DYNAMODB_TABLE_NAME')}")
    if os.getenv("REPOSITORY_TYPE") == "dynamodb":
        print("Using DynamoDBEntryRepository")
        from app.repositories.dynamodb_entry_repository import DynamoDBEntryRepository
        return DynamoDBEntryRepository(os.environ["DYNAMODB_TABLE_NAME"])
    print("Using InMemoryEntryRepository")
    return InMemoryEntryRepository()


@lru_cache
def _embedding_port() -> EmbeddingPort:
    if os.getenv("EMBEDDING_TYPE") == "openai":
        from app.embedding.openai_embedding_client import OpenAIEmbeddingClient
        return OpenAIEmbeddingClient()
    from app.embedding.in_memory_embedding_client import InMemoryEmbeddingClient
    return InMemoryEmbeddingClient()


@lru_cache
def _vector_repository() -> VectorRepository:
    if os.getenv("VECTOR_REPOSITORY_TYPE") == "pinecone":
        from app.repositories.pinecone_vector_repository import PineconeVectorRepository
        return PineconeVectorRepository()
    from app.repositories.in_memory_vector_repository import InMemoryVectorRepository
    return InMemoryVectorRepository()


def get_service() -> EntryService:
    return EntryService(_repository(), _embedding_port(), _vector_repository())


def get_current_user_id(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return os.getenv("DEV_USER_ID", "dev-user")
