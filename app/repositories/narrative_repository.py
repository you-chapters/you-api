import boto3
from abc import ABC, abstractmethod

from app.models.narrative import NarrativeSummary
from app.models.phase import PhaseIndex, PhaseRecord


class NarrativeRepository(ABC):
    @abstractmethod
    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None: ...

    @abstractmethod
    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None: ...

    @abstractmethod
    def get_phase(self, user_id: str, phase_id: str) -> PhaseRecord | None: ...

    @abstractmethod
    def save_phase(self, user_id: str, phase_id: str, record: PhaseRecord) -> None: ...

    @abstractmethod
    def batch_get_phases(self, user_id: str, phase_ids: list[str]) -> list[PhaseRecord]: ...

    @abstractmethod
    def get_phase_index(self, user_id: str) -> PhaseIndex | None: ...

    @abstractmethod
    def save_phase_index(self, user_id: str, index: PhaseIndex) -> None: ...


class DynamoDBNarrativeRepository(NarrativeRepository):
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._table_name = table_name

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

    def get_phase(self, user_id: str, phase_id: str) -> PhaseRecord | None:
        response = self._table.get_item(Key={"user_id": user_id, "record_id": f"phase#{phase_id}"})
        item = response.get("Item")
        if not item:
            return None
        item.pop("user_id", None)
        item.pop("record_id", None)
        return PhaseRecord(**item)

    def save_phase(self, user_id: str, phase_id: str, record: PhaseRecord) -> None:
        self._table.put_item(Item={
            "user_id": user_id,
            "record_id": f"phase#{phase_id}",
            **record.model_dump(),
        })

    def batch_get_phases(self, user_id: str, phase_ids: list[str]) -> list[PhaseRecord]:
        if not phase_ids:
            return []
        dynamodb = boto3.resource("dynamodb")
        keys = [{"user_id": user_id, "record_id": f"phase#{pid}"} for pid in phase_ids]
        response = dynamodb.batch_get_item(RequestItems={self._table_name: {"Keys": keys}})
        items = response.get("Responses", {}).get(self._table_name, [])
        records = []
        for item in items:
            item.pop("user_id", None)
            item.pop("record_id", None)
            records.append(PhaseRecord(**item))
        records.sort(key=lambda r: r.start_date)
        return records

    def get_phase_index(self, user_id: str) -> PhaseIndex | None:
        response = self._table.get_item(Key={"user_id": user_id, "record_id": "phase_index#latest"})
        item = response.get("Item")
        if not item:
            return None
        item.pop("user_id", None)
        item.pop("record_id", None)
        return PhaseIndex(**item)

    def save_phase_index(self, user_id: str, index: PhaseIndex) -> None:
        self._table.put_item(Item={
            "user_id": user_id,
            "record_id": "phase_index#latest",
            **index.model_dump(),
        })
