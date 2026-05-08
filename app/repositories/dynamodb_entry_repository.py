import boto3

from app.models.entry import Entry
from app.repositories.entry_repository import EntryRepository


class DynamoDBEntryRepository(EntryRepository):
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def save(self, entry: Entry) -> None:
        raise NotImplementedError

    def get(self, entry_id: str) -> Entry | None:
        raise NotImplementedError

    def list_by_user(self, user_id: str) -> list[Entry]:
        raise NotImplementedError
