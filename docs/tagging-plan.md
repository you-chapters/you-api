# Tagging Feature — Implementation Plan (v2)

## Context

Entries currently have no semantic metadata beyond raw text. This feature adds auto-generated structured tags (people, locations, topics, mood, time markers) extracted via LLM — stored in DynamoDB, included in embeddings, and returned through all existing API responses. Tags are the structured metadata layer that makes the journal queryable: filter by topic, cluster by life phase, and enrich LLM context for RAG queries like "what was I focused on before I changed jobs."

---

## Data model

### New: `app/models/entry_tags.py`
```python
class EntryTags(BaseModel):
    people: list[str] = Field(default_factory=list)       # normalized names, e.g. "Alice Smith"
    locations: list[str] = Field(default_factory=list)    # user-provided + LLM-extracted
    topics: list[str] = Field(default_factory=list)       # work, family, health, travel, etc.
    mood: str | None = None                               # positive | negative | neutral | mixed
    time_markers: list[str] = Field(default_factory=list) # events at a different time than entry date
```

**Why time_markers:** entries have a write timestamp, but often reference events at a different time — "last week I visited Paris", "in June I started the new job." Time markers track *when things happened*, not when you wrote. This enables timeline reconstruction and temporal RAG queries.

### Modified: `app/models/entry.py`
```python
class CreateEntryRequest(BaseModel):
    entry: str = Field(max_length=10_000)
    location: str | None = None  # user's physical location when writing

class Entry(BaseModel):
    user_id: str
    timestamp: str
    entry_id: str
    entry: str
    location: str | None = None   # stored; passed to tag extractor
    tags: EntryTags | None = None  # None until async extraction completes
```

`tags: None` is backward-compatible — existing DynamoDB items without `tags` deserialize fine.

---

## Tag extraction pipeline (Streams Lambda)

Both tag extraction and embedding happen in `handler_embedding.py` — **sequential** (tags must precede embedding so tags enrich the embedded text):

```
INSERT event
  → extract tags(entry_text, timestamp, user_location) via LLM
  → build augmented text:
      "Date: {ts}
       Topics: work, health
       People: Alice Smith
       Mood: positive
       Location: New York

       {entry_text}"
  → embed augmented text
  → upsert Pinecone with tags in metadata: {user_id, timestamp, topics, mood, people, locations}
  → update_item on DynamoDB with tags
```

**Why tags before embedding:** searching "family tension" will match entries tagged `topics:family, mood:negative` even if those exact words don't appear. Richer vectors for free.

**Why sequential (not parallel):** The Lambda runs async from the user's perspective. Parallel (ThreadPoolExecutor) adds complexity for minimal gain since the 60s Lambda timeout is plenty for two sequential LLM calls. Keep it simple.

The Lambda writes tags back via `update_item` — safe because it only handles `INSERT` events, so the subsequent `UPDATE` doesn't re-trigger it.

---

## Tag extraction adapter

Follows the existing port/adapter pattern:

| File | Role |
|------|------|
| `app/tag_extraction/tag_extraction_port.py` | ABC: `extract(text, timestamp, user_location) -> EntryTags` |
| `app/tag_extraction/openai_tag_extraction_client.py` | `gpt-4o-mini` with JSON response format; reuses existing `OPENAI_API_KEY` |
| `app/tag_extraction/in_memory_tag_extraction_client.py` | Returns empty `EntryTags()` for local dev |

The LLM is instructed to:
- Use the most complete/consistent name form (always "Alice Smith", not sometimes "my friend") — foundation for canonical person IDs later
- Merge user-provided location with text-extracted locations (not override)
- Normalize topics to a controlled vocabulary: `work, family, travel, health, reading, finance, relationships, hobbies, food, exercise`

`app/handler_embedding.py` gets a module-level `@lru_cache` factory (same pattern as `_embedding_client`):
```python
@lru_cache
def _tag_extraction_port() -> TagExtractionClient:
    return OpenAITagExtractionClient()
```

---

## API changes

Tags appear in all existing responses automatically — `Entry` serializes `tags` to JSON. No new endpoints required for core feature.

No new filtering endpoints. Tags are returned in all existing responses. Filtering by tag (topic, mood, people) is the natural next layer — done properly as a Pinecone-side filter extension to `search_entries`, not as a weak post-fetch Python filter on `GET /entries`.

---

## Infrastructure changes (`infra/stacks/api_stack.py`)

```python
# Add to YouEmbeddingFunction env vars:
"DYNAMODB_TABLE_NAME": table.table_name,
"TAG_EXTRACTION_TYPE": "openai",   # future: in-memory fallback

# Add DynamoDB write permission (currently none for embedding Lambda):
table.grant_write_data(embedding_function)
```

---

## Files to create/modify

| File | Change |
|------|--------|
| `app/models/entry_tags.py` | **New** — `EntryTags` Pydantic model |
| `app/tag_extraction/tag_extraction_port.py` | **New** — ABC |
| `app/tag_extraction/openai_tag_extraction_client.py` | **New** — OpenAI/gpt-4o-mini JSON impl |
| `app/tag_extraction/in_memory_tag_extraction_client.py` | **New** — returns empty tags |
| `app/models/entry.py` | Add `location` to `CreateEntryRequest`; add `location`, `tags` to `Entry` |
| `app/routers/entries.py` | Add `location` to create body |
| `app/handler_embedding.py` | Sequential: extract tags → augmented embed → Pinecone → DynamoDB write-back |
| `infra/stacks/api_stack.py` | DynamoDB write permission + env vars for embedding Lambda |
| `tests/test_handler_embedding.py` | Tag extraction, augmented text, DynamoDB write-back |
| `tests/test_entries_router.py` | `location` in create tests |
| `tests/test_openai_tag_extraction_client.py` | **New** — patch OpenAI client |
| `tests/test_in_memory_tag_extraction_client.py` | **New** — basic coverage |
| `app/repositories/vector_repository.py` | Add `tags` param to `upsert` ABC |
| `app/repositories/pinecone_vector_repository.py` | Include tags in Pinecone metadata |
| `app/repositories/in_memory_vector_repository.py` | Accept (and ignore) tags param for parity |
| `tests/test_pinecone_vector_repository.py` | Verify tags appear in metadata payload |
| `tests/test_in_memory_vector_repository.py` | Accept tags without breaking existing tests |

---

### VectorRepository signature change

`upsert` gains an optional `tags` parameter:
```python
# app/repositories/vector_repository.py (ABC)
def upsert(self, entry_id, user_id, vector, timestamp_unix, tags: EntryTags | None = None) -> None

# PineconeVectorRepository stores tags as flat Pinecone metadata:
metadata = {
    "user_id": user_id,
    "timestamp": timestamp_unix,
    "topics": tags.topics if tags else [],       # list[str] — Pinecone supports this
    "mood": tags.mood if tags else None,
    "people": tags.people if tags else [],
    "locations": tags.locations if tags else [],
}
```

This enables future `search_entries` extensions with Pinecone-side filters (e.g., `{"topics": {"$in": ["work"]}}`).

---

## Future extensions (out of scope now)

| Idea | Notes |
|------|-------|
| **People registry** | Separate DynamoDB table mapping nicknames/aliases to canonical person IDs + `/people` CRUD API. Natural next step once consistent name extraction proves useful. |
| **Multi-dimension filtering** | `?people=Alice&mood=positive` — extend the topic filter pattern; Pinecone metadata makes this efficient |
| **Tag-aware semantic search** | Extend `search_entries` to accept `topic`/`mood`/`people` filters applied at Pinecone query level — the right way to filter, replaces the naive list filter |
| **Tag editing** | PATCH endpoint to correct auto-extracted tags |
| **Life phase clustering** | Batch job that groups entries by dominant topics over time windows |

---

## Verification

1. `uv run pytest` — all tests pass including new ones (coverage ≥ 80%)
2. `make run-mem` — `POST /entries` with `{"entry": "...", "location": "NYC"}` returns `{"tags": null}` (async not yet run locally)
3. End-to-end with `REPOSITORY_TYPE=dynamodb`: create entry → wait a few seconds → `GET /entries/{id}` shows populated `tags` struct
4. Pinecone record for the entry has `topics`, `mood`, `people`, `locations` in metadata
5. `cd infra && cdk diff` — only permissions + env var changes on `YouEmbeddingFunction`