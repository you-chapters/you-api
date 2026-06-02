import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.logging_config import get_logger

logger = get_logger(__name__)

_ACTIVE_USER_DAYS = 90


def _make_service():
    from app.dependencies import _llm_client, _narrative_repository, _repository
    from app.services.phase_service import PhaseService
    return PhaseService(_repository(), _narrative_repository(), _llm_client())


@lru_cache
def _entries_table():
    import boto3
    return boto3.resource("dynamodb").Table(os.environ["ENTRIES_TABLE_NAME"])


def _distinct_user_ids() -> set[str]:
    table = _entries_table()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_ACTIVE_USER_DAYS)).isoformat()
    user_ids: set[str] = set()
    scan_kwargs = dict(
        ProjectionExpression="user_id",
        FilterExpression="#ts >= :cutoff",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={":cutoff": cutoff},
    )
    response = table.scan(**scan_kwargs)
    while True:
        for item in response["Items"]:
            user_ids.add(item["user_id"])
        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(**scan_kwargs, ExclusiveStartKey=response["LastEvaluatedKey"])
    return user_ids


def handler(event, context):
    user_ids = _distinct_user_ids()
    service = _make_service()
    logger.info("Detecting phases for %d users", len(user_ids))
    for user_id in user_ids:
        try:
            service.detect_and_store(user_id)
        except Exception:
            logger.exception("Phase detection failed for user %s", user_id)
    logger.info("Phase detection complete")
