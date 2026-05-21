import boto3
from abc import ABC, abstractmethod

from app.models.narrative import NarrativeSummary


class NarrativeRepository(ABC):
    @abstractmethod
    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None: ...

    @abstractmethod
    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None: ...


class DynamoDBNarrativeRepository(NarrativeRepository):
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None:
        response = self._table.get_item(Key={"user_id": user_id, "record_id": record_id})
        item = response.get("Item")
        if not item:
            return None
        item.pop("user_id", None)
        item.pop("record_id", None)
        return NarrativeSummary(**item)

    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None:
        self._table.put_item(Item={
            "user_id": user_id,
            "record_id": record_id,
            **summary.model_dump(exclude={"is_cached"}),
        })
