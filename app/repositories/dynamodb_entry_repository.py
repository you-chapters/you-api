import boto3
from boto3.dynamodb.conditions import Key

from app.models.entry import Entry
from app.repositories.entry_repository import EntryRepository


class DynamoDBEntryRepository(EntryRepository):
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def save(self, entry: Entry) -> None:
        self._table.put_item(Item=entry.model_dump())

    def get(self, user_id: str, entry_id: str) -> Entry | None:
        response = self._table.get_item(Key={"user_id": user_id, "entry_id": entry_id})
        item = response.get("Item")
        return Entry(**item) if item else None

    def list_by_user(self, user_id: str) -> list[Entry]:
        response = self._table.query(KeyConditionExpression=Key("user_id").eq(user_id))
        return [Entry(**item) for item in response["Items"]]