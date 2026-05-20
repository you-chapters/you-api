# Phase 2 — Dashboard: Backend Implementation

Adds a `GET /entries/summary` endpoint that aggregates tag data from existing DynamoDB entries
into a period summary for the dashboard homepage.

No new infrastructure required — no GSI, no new table, no new Lambda.
The existing `list_by_user` query fetches all user entries; this endpoint filters and aggregates
in Python.

---

## New files

### `app/models/summary.py`

```python
from pydantic import BaseModel


class MoodPoint(BaseModel):
    date: str   # "YYYY-MM-DD", one per day that has an entry with a mood
    mood: str   # "positive" | "negative" | "neutral" | "mixed"


class TopicCount(BaseModel):
    topic: str
    count: int


class PersonCount(BaseModel):
    name: str
    count: int


class PeriodSummary(BaseModel):
    period_days: int
    entry_count: int
    mood_timeline: list[MoodPoint]   # chronological, one per day
    top_topics: list[TopicCount]     # sorted by count desc
    top_people: list[PersonCount]    # sorted by count desc
```

---

## Modified files

### `app/services/entry_service.py`

Add one import and one new method. No changes to existing methods.

New import at top:
```python
from datetime import timedelta
from collections import Counter
from app.models.summary import MoodPoint, PeriodSummary
```

New method on `EntryService`:
```python
def get_summary(self, user_id: str, period_days: int = 30) -> PeriodSummary:
    all_entries = self._repository.list_by_user(user_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()
    entries = [e for e in all_entries if e.timestamp >= cutoff]

    topic_counter: Counter[str] = Counter()
    person_counter: Counter[str] = Counter()
    mood_by_date: dict[str, str] = {}

    for entry in entries:
        if entry.tags is None:
            continue
        topic_counter.update(entry.tags.topics)
        person_counter.update(entry.tags.people)
        if entry.tags.mood:
            date = entry.timestamp[:10]  # "YYYY-MM-DD"
            mood_by_date[date] = entry.tags.mood  # last entry of the day wins

    return PeriodSummary(
        period_days=period_days,
        entry_count=len(entries),
        mood_timeline=[
            MoodPoint(date=d, mood=m)
            for d, m in sorted(mood_by_date.items())
        ],
        top_topics=[
            TopicCount(topic=t, count=c)
            for t, c in topic_counter.most_common()
        ],
        top_people=[
            PersonCount(name=n, count=c)
            for n, c in person_counter.most_common()
        ],
    )
```

Notes on the aggregation logic:
- ISO-8601 strings are lexicographically sortable so `timestamp >= cutoff` works as a range filter.
- Entries where `tags` is still `None` (processing not yet complete) are skipped cleanly.
- If a day has multiple entries with different moods, the one written last wins (list is already
  sorted newest-first by `list_by_user`, but since we overwrite by date key, the last write wins
  — consider sorting oldest-first before building `mood_by_date` if you want last-of-day instead).
- `period_days` query param defaults to 30; client can request 7 for the weekly view.

### `app/routers/entries.py`

Add one import and one new route. No changes to existing routes.

New import:
```python
from app.models.summary import PeriodSummary
```

New route (add before the `/{entry_id}` route to avoid shadowing):
```python
@router.get("/summary", response_model=PeriodSummary)
def get_summary(
    period: int = 30,
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_service),
) -> PeriodSummary:
    return service.get_summary(user_id, period_days=period)
```

**Important:** place `GET /summary` before `GET /{entry_id}` in the file — FastAPI matches routes
top-to-bottom and would otherwise interpret the literal string `"summary"` as an `entry_id` path
parameter.

---

## API contract

```
GET /entries/summary?period=7
GET /entries/summary?period=30   (default)

Authorization: Bearer <cognito-id-token>

Response 200:
{
  "period_days": 7,
  "entry_count": 4,
  "mood_timeline": [
    { "date": "2026-05-18", "mood": "positive" },
    { "date": "2026-05-20", "mood": "mixed" }
  ],
  "top_topics": [
    { "topic": "work",   "count": 3 },
    { "topic": "health", "count": 2 },
    { "topic": "food",   "count": 1 }
  ],
  "top_people": [
    { "name": "Н", "count": 2 }
  ]
}
```

---

## Scalability note

`list_by_user` issues a DynamoDB `Query` on the partition key, fetching all items for the user.
It has no pagination (`LastEvaluatedKey` not handled) — at 1 MB this silently truncates (~500–1000
entries). For a personal diary this is fine for a long time. When you're ready to fix it, add
pagination to `DynamoDBEntryRepository.list_by_user` or add a GSI on `timestamp` and query with
a date range directly. Either way, that's a repository-layer change transparent to the service.