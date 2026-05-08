import os
from functools import lru_cache

from app.repositories.entry_repository import EntryRepository
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.services.entry_service import EntryService


@lru_cache
def _repository() -> EntryRepository:
    if os.getenv("REPOSITORY_TYPE") == "dynamodb":
        from app.repositories.dynamodb_entry_repository import DynamoDBEntryRepository
        return DynamoDBEntryRepository(os.environ["DYNAMODB_TABLE_NAME"])
    return InMemoryEntryRepository()


def get_service() -> EntryService:
    return EntryService(_repository())
