import os
from functools import lru_cache

from app.repositories.entry_repository import EntryRepository
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
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


def get_service() -> EntryService:
    return EntryService(_repository())


def get_current_user_id() -> str:
    # TODO: replace with real auth (extract from JWT/session)
    return "user-1"
