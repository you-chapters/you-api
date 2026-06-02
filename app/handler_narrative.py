import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.logging_config import get_logger

logger = get_logger(__name__)

_ACTIVE_USER_DAYS = 90


def _make_service():
    from app.dependencies import _repository, _narrative_repository, _llm_client
    from app.services.narrative_service import NarrativeService
    return NarrativeService(_repository(), _narrative_repository(), _llm_client())


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
    period_type = event.get("type", "week")
    today = datetime.now(timezone.utc).date()

    if period_type == "week":
        period_key = today.strftime("%G-W%V")
    else:
        first_of_month = today.replace(day=1)
        period_key = (first_of_month - timedelta(days=1)).strftime("%Y-%m")

    user_ids = _distinct_user_ids()
    service = _make_service()

    logger.info("Generating narratives for %d users for period '%s' '%s'", len(user_ids), period_type, period_key)
    for user_id in user_ids:
        try:
            service.get_narrative(user_id, period_type=period_type, period_key=period_key, force_refresh=True)
        except Exception:
            logger.exception("Narrative generation failed for user %s", user_id)
    logger.info("Narratives generated")
