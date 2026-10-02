import time
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError


class UsageLimiter(ABC):
    @abstractmethod
    def allow(self, user_id: str, operation: str) -> bool: ...


class InMemoryUsageLimiter(UsageLimiter):
    def __init__(self, limits: dict[str, int]) -> None:
        self._limits = limits
        self._counts: dict[tuple[str, str, int], int] = {}

    def allow(self, user_id: str, operation: str) -> bool:
        bucket = int(time.time() // 60)
        key = (user_id, operation, bucket)
        count = self._counts.get(key, 0)
        if count >= self._limits[operation]:
            return False
        self._counts[key] = count + 1
        return True


class DynamoDBUsageLimiter(UsageLimiter):
    def __init__(self, table_name: str, limits: dict[str, int]) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._limits = limits

    def allow(self, user_id: str, operation: str) -> bool:
        now = int(time.time())
        bucket = now // 60
        try:
            self._table.update_item(
                Key={"user_id": user_id, "bucket": f"{operation}#{bucket}"},
                UpdateExpression="ADD #count :one SET expires_at = :expires_at",
                ConditionExpression="attribute_not_exists(#count) OR #count < :limit",
                ExpressionAttributeNames={"#count": "count"},
                ExpressionAttributeValues={":one": 1, ":limit": self._limits[operation], ":expires_at": now + 120},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True
