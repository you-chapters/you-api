import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.models.entry import Entry
from app.repositories.entry_repository import EntryRepository


class DynamoDBEntryRepository(EntryRepository):
    def __init__(self, table_name: str) -> None:
        self._resource = boto3.resource("dynamodb")
        self._table = self._resource.Table(table_name)

    def save(self, entry: Entry) -> None:
        self._table.put_item(Item=entry.model_dump())

    def get(self, user_id: str, entry_id: str) -> Entry | None:
        response = self._table.get_item(Key={"user_id": user_id, "entry_id": entry_id})
        item = response.get("Item")
        return Entry(**item) if item else None

    def list_by_user(self, user_id: str, from_ts: str | None = None, to_ts: str | None = None) -> list[Entry]:
        kwargs: dict = {"KeyConditionExpression": Key("user_id").eq(user_id)}
        filter_expr = None
        if from_ts is not None:
            filter_expr = Attr("timestamp").gte(from_ts)
        if to_ts is not None:
            cond = Attr("timestamp").lt(to_ts)
            filter_expr = filter_expr & cond if filter_expr else cond
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr
        response = self._table.query(**kwargs)
        return [Entry(**item) for item in response["Items"]]

    def get_many(self, user_id: str, entry_ids: list[str]) -> list[Entry]:
        if not entry_ids:
            return []
        keys = [{"user_id": user_id, "entry_id": eid} for eid in entry_ids]
        response = self._resource.batch_get_item(
            RequestItems={self._table.name: {"Keys": keys}}
        )
        items = response["Responses"].get(self._table.name, [])
        return [Entry(**item) for item in items]