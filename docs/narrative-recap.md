# Narrative Recap — Backend Implementation

Free-form LLM prose narratives (ISO week + monthly) cached in a dedicated DynamoDB table.
Current period refreshes daily; past periods are frozen once closed.
Designed as the data foundation for Phase 3 phase detection.

Two delivery stages — implement independently:
- **Stage 1 (lazy)** — on-demand via API endpoint; generates on first request, caches
- **Stage 2 (scheduled)** — EventBridge cron Lambda; fills gaps for users who didn't open the app

---

## Breaking change: env var rename

`DYNAMODB_TABLE_NAME` → `ENTRIES_TABLE_NAME` everywhere.

Files to update:
- `infra/stacks/api_stack.py` — env dict on `YouApiFunction` and `YouEmbeddingFunction`
- `app/dependencies.py` — `os.environ["ENTRIES_TABLE_NAME"]`

---

## New DynamoDB table: `you_narratives`

### `infra/stacks/dynamodb_stack.py`

Add alongside the entries table:

```python
self.narratives_table = dynamodb.Table(
    self,
    "NarrativesTable",
    table_name="you_narratives",
    partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
    sort_key=dynamodb.Attribute(name="record_id", type=dynamodb.AttributeType.STRING),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.RETAIN,
)
```

SK values:
- `cache#week#2026-W21` — weekly narrative cache
- `cache#month#2026-05` — monthly narrative cache
- `phase#<uuid>` — future Phase 3 phase records

### `infra/stacks/api_stack.py`

```python
def __init__(self, ..., *, table, narratives_table, user_pool, ...):
    ...
    fn = PythonFunction(
        ...,
        environment={
            "ENTRIES_TABLE_NAME": table.table_name,       # renamed from DYNAMODB_TABLE_NAME
            "NARRATIVES_TABLE_NAME": narratives_table.table_name,
            "LLM_TYPE": "openai",
            ...
        },
    )
    narratives_table.grant_read_write_data(fn)
```

### `infra/app.py`

```python
ApiStack(app, "YouApiApiStack",
    table=dynamo_stack.table,
    narratives_table=dynamo_stack.narratives_table,
    user_pool=cognito_stack.user_pool,
)
```

---

## New files

### `app/models/narrative.py`

```python
from typing import Literal
from pydantic import BaseModel

class NarrativeSummary(BaseModel):
    period_type: Literal["week", "month"]
    period_key: str        # "2026-W21" or "2026-05"
    entry_count: int
    text: str              # free-form LLM prose
    generated_at: str      # ISO-8601 UTC
    is_cached: bool
```

### `app/llm/llm_client.py`

```python
from abc import ABC, abstractmethod
from app.models.entry import Entry

class LLMClient(ABC):
    @abstractmethod
    def generate_narrative(self, entries: list[Entry], period_label: str) -> str:
        ...
```

### `app/llm/openai_llm_client.py`

```python
from openai import OpenAI
from app.config import get_secret
from app.llm.llm_client import LLMClient
from app.models.entry import Entry

_MODEL = "gpt-4o-mini"
_SYSTEM_PROMPT = (
    "You are a thoughtful personal journal assistant. "
    "Write a warm, reflective, first-person narrative paragraph summarizing the provided diary entries. "
    "Write freely — no fixed structure, no bullet points. "
    "Speak as if the person is looking back at their own period. "
    "3–5 sentences."
)

class OpenAILLMClient(LLMClient):
    def __init__(self) -> None:
        self._client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))

    def generate_narrative(self, entries: list[Entry], period_label: str) -> str:
        if not entries:
            return "No entries this period."
        body = "\n\n".join(
            f"[{e.timestamp[:10]}] {e.entry}"
            for e in sorted(entries, key=lambda e: e.timestamp)
        )
        response = self._client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Period: {period_label}\n\n{body}"},
            ],
        )
        return response.choices[0].message.content or ""
```

### `app/llm/in_memory_llm_client.py`

```python
from app.llm.llm_client import LLMClient
from app.models.entry import Entry

class InMemoryLLMClient(LLMClient):
    def generate_narrative(self, entries: list[Entry], period_label: str) -> str:
        return f"Stub narrative for {period_label} ({len(entries)} entries)."
```

### `app/repositories/narrative_repository.py`

```python
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
```

### `app/repositories/in_memory_narrative_repository.py`

```python
from app.models.narrative import NarrativeSummary
from app.repositories.narrative_repository import NarrativeRepository

class InMemoryNarrativeRepository(NarrativeRepository):
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], NarrativeSummary] = {}

    def get(self, user_id: str, record_id: str) -> NarrativeSummary | None:
        return self._store.get((user_id, record_id))

    def save(self, user_id: str, record_id: str, summary: NarrativeSummary) -> None:
        self._store[(user_id, record_id)] = summary
```

### `app/services/narrative_service.py`

```python
from datetime import datetime, timedelta, timezone
from app.llm.llm_client import LLMClient
from app.models.narrative import NarrativeSummary
from app.repositories.entry_repository import EntryRepository
from app.repositories.narrative_repository import NarrativeRepository

class NarrativeService:
    def __init__(
        self,
        entry_repo: EntryRepository,
        narrative_repo: NarrativeRepository,
        llm_client: LLMClient,
    ) -> None:
        self._entries = entry_repo
        self._narratives = narrative_repo
        self._llm = llm_client

    def get_narrative(
        self,
        user_id: str,
        period_type: str,   # "week" | "month"
        period_key: str,    # "2026-W21" | "2026-05"
        force_refresh: bool = False,
    ) -> NarrativeSummary:
        record_id = f"cache#{period_type}#{period_key}"
        is_current = self._is_current_period(period_type, period_key)

        if not force_refresh:
            cached = self._narratives.get(user_id, record_id)
            if cached:
                stale = is_current and cached.generated_at[:10] != datetime.now(timezone.utc).date().isoformat()
                if not stale:
                    return cached.model_copy(update={"is_cached": True})

        entries = self._entries_for_period(user_id, period_type, period_key)
        text = self._llm.generate_narrative(entries, period_key)

        summary = NarrativeSummary(
            period_type=period_type,
            period_key=period_key,
            entry_count=len(entries),
            text=text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            is_cached=False,
        )
        self._narratives.save(user_id, record_id, summary)
        return summary

    def _is_current_period(self, period_type: str, period_key: str) -> bool:
        today = datetime.now(timezone.utc).date()
        if period_type == "week":
            return period_key == today.strftime("%G-W%V")
        return period_key == today.strftime("%Y-%m")

    def _entries_for_period(self, user_id: str, period_type: str, period_key: str) -> list:
        all_entries = self._entries.list_by_user(user_id)
        if period_type == "week":
            year, week = int(period_key[:4]), int(period_key[6:])
            monday = datetime.fromisocalendar(year, week, 1).replace(tzinfo=timezone.utc)
            sunday = monday + timedelta(days=7)
            return [e for e in all_entries
                    if monday.isoformat() <= e.timestamp < sunday.isoformat()]
        # month
        return [e for e in all_entries if e.timestamp[:7] == period_key]
```

---

## Modified files

### `app/routers/entries.py`

Add before the `/{entry_id}` catch-all:

```python
from datetime import datetime, timezone
from app.models.narrative import NarrativeSummary
from app.services.narrative_service import NarrativeService
from app.dependencies import get_narrative_service

@router.get("/narrative", response_model=NarrativeSummary)
def get_narrative(
    type: str = "week",
    key: str | None = None,
    refresh: bool = False,
    user_id: str = Depends(get_current_user_id),
    service: NarrativeService = Depends(get_narrative_service),
) -> NarrativeSummary:
    today = datetime.now(timezone.utc).date()
    resolved_key = key or (
        today.strftime("%G-W%V") if type == "week" else today.strftime("%Y-%m")
    )
    return service.get_narrative(user_id, period_type=type, period_key=resolved_key, force_refresh=refresh)
```

### `app/dependencies.py`

```python
# rename existing:
os.environ["ENTRIES_TABLE_NAME"]   # was DYNAMODB_TABLE_NAME

# add:
@lru_cache
def _llm_client() -> LLMClient:
    if os.getenv("LLM_TYPE") == "openai":
        from app.llm.openai_llm_client import OpenAILLMClient
        return OpenAILLMClient()
    from app.llm.in_memory_llm_client import InMemoryLLMClient
    return InMemoryLLMClient()

@lru_cache
def _narrative_repository() -> NarrativeRepository:
    if table_name := os.getenv("NARRATIVES_TABLE_NAME"):
        from app.repositories.narrative_repository import DynamoDBNarrativeRepository
        return DynamoDBNarrativeRepository(table_name)
    from app.repositories.in_memory_narrative_repository import InMemoryNarrativeRepository
    return InMemoryNarrativeRepository()

def get_narrative_service() -> NarrativeService:
    return NarrativeService(_repository(), _narrative_repository(), _llm_client())
```

---

## Stage 1 verification

1. `GET /entries/narrative` → current week, `is_cached: false` on first call
2. Second call same day → `is_cached: true`, same `generated_at`
3. `?refresh=true` → regenerates, new `generated_at`, `is_cached: false`
4. `?type=month` → current month narrative
5. `?type=week&key=2026-W20` → past week, frozen after first generation
6. No entries in period → returns `"No entries this period."` without calling LLM
7. `grep -r DYNAMODB_TABLE_NAME .` returns no results after rename

---

## Stage 2 — Scheduled generation

Runs automatically on a cron schedule to ensure every period has a narrative even if the user
never opened the app. Uses the same `NarrativeService` — no new business logic.

### Schedule

| Trigger | Cron (UTC) | Generates |
|---------|-----------|-----------|
| Weekly  | Sunday 23:55 | Current ISO week (Mon–Sun, still open) |
| Monthly | 1st of month 00:05 | Previous month (just closed) |

The weekly run captures the complete week before it becomes past. The monthly run fires after
midnight on the 1st so the previous month is already frozen.

### New file: `app/handler_narrative.py`

```python
import os
import boto3
from datetime import datetime, timedelta, timezone


def handler(event, context):
    period_type = event.get("type", "week")
    today = datetime.now(timezone.utc).date()

    if period_type == "week":
        period_key = today.strftime("%G-W%V")
    else:
        first_of_month = today.replace(day=1)
        period_key = (first_of_month - timedelta(days=1)).strftime("%Y-%m")

    user_ids = _distinct_user_ids()

    from app.dependencies import _repository, _narrative_repository, _llm_client
    from app.services.narrative_service import NarrativeService

    service = NarrativeService(_repository(), _narrative_repository(), _llm_client())

    for user_id in user_ids:
        try:
            service.get_narrative(user_id, period_type=period_type, period_key=period_key)
        except Exception as e:
            print(f"narrative generation failed for user {user_id}: {e}")


_ACTIVE_USER_DAYS = 90  # skip users with no entries in this window


def _distinct_user_ids() -> set[str]:
    table = boto3.resource("dynamodb").Table(os.environ["ENTRIES_TABLE_NAME"])
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
```

`force_refresh=False` (default) means the service is a no-op for users who already have a
fresh cached narrative — no redundant LLM calls.

### CDK additions in `infra/stacks/api_stack.py`

```python
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets

narrative_fn = PythonFunction(
    self,
    "YouNarrativeFunction",
    entry=str(REPO_ROOT),
    index="app/handler_narrative.py",
    handler="handler",
    runtime=lambda_.Runtime.PYTHON_3_13,
    memory_size=512,
    timeout=Duration.minutes(5),
    environment={
        "ENTRIES_TABLE_NAME": table.table_name,
        "NARRATIVES_TABLE_NAME": narratives_table.table_name,
        "LLM_TYPE": "openai",
        **shared_env,
    },
)

table.grant_read_data(narrative_fn)
narratives_table.grant_read_write_data(narrative_fn)
for param in ssm_params:
    param.grant_read(narrative_fn)

events.Rule(
    self, "WeeklyNarrativeRule",
    schedule=events.Schedule.cron(minute="55", hour="23", week_day="SUN"),
    targets=[targets.LambdaFunction(
        narrative_fn,
        event=events.RuleTargetInput.from_object({"type": "week"}),
    )],
)

events.Rule(
    self, "MonthlyNarrativeRule",
    schedule=events.Schedule.cron(minute="5", hour="0", day="1"),
    targets=[targets.LambdaFunction(
        narrative_fn,
        event=events.RuleTargetInput.from_object({"type": "month"}),
    )],
)
```

### Stage 2 verification

1. Invoke `handler_narrative.handler({"type": "week"}, None)` locally → narratives generated for all users in entries table
2. Invoke with `{"type": "month"}` on the 1st → previous month narrative generated, frozen
3. Invoke twice same day → second call is a no-op (served from cache), no extra LLM calls
4. CDK diff shows two new EventBridge rules and `YouNarrativeFunction`