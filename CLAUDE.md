# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# you-api

FastAPI + AWS Lambda + DynamoDB entries API.

## Stack

- Python 3.13, FastAPI, Mangum (Lambda adapter), boto3, Pydantic v2
- Infrastructure: AWS CDK (Python) in `infra/`
- Package manager: `uv`

## Commands

```bash
uv sync                # install deps (first time or after uv.lock changes)

make run-mem           # in-memory (no AWS)
make run               # DynamoDB test table
make run-prod          # DynamoDB prod table

uv run pytest                                          # run all tests
uv run pytest tests/test_entry_service.py::test_name  # single test
uv run pytest tests/ -v --cov-report=term-missing     # with line-level coverage

# One-time Pinecone index setup (prints PINECONE_INDEX_HOST for SSM)
PINECONE_API_KEY=xxx uv run python scripts/setup_pinecone.py

# Before CDK deploy: regenerate requirements.txt from uv.lock
uv export --no-dev --output-file requirements.txt

cd infra && pip install -r requirements.txt  # one-time, infra has its own venv
cd infra && cdk deploy --all
```

## Architecture

**Three Lambda functions:**
- `handler_entries.py` — wraps FastAPI via Mangum; handles all HTTP CRUD
- `handler_embedding.py` — DynamoDB Streams consumer; runs on `INSERT` only; sequential pipeline: extract tags → build augmented text → embed → upsert Pinecone → write tags back to DynamoDB
- `handler_narrative.py` — EventBridge cron; generates weekly/monthly narratives for all active users

**Write path is non-blocking:** entries are saved to DynamoDB first; embeddings/tags happen in the background via Streams. Tags are never set via the HTTP API; they are always `null` until the embedding Lambda writes them back.

**Adapters behind ABCs, selected by env vars at startup, singletons via `@lru_cache`:**
- `REPOSITORY_TYPE=dynamodb` → `DynamoDBEntryRepository`, else `InMemoryEntryRepository`
- `EMBEDDING_TYPE=openai` → `OpenAIEmbeddingClient`, else `InMemoryEmbeddingClient`
- `VECTOR_REPOSITORY_TYPE=pinecone` → `PineconeVectorRepository`, else `InMemoryVectorRepository`
- `TAG_EXTRACTION_TYPE=openai` → `OpenAITagExtractionClient`, else `InMemoryTagExtractionClient` (returns empty tags) — used only by the embedding Lambda
- `LLM_TYPE=openai` → `OpenAILLMClient` (`gpt-4o-mini`), else `InMemoryLLMClient` (stub) — used only by the HTTP handler for narrative generation
- `NARRATIVES_TABLE_NAME` presence (not a type flag) → `DynamoDBNarrativeRepository`, else `InMemoryNarrativeRepository`

`handler_entries.py` and `handler_embedding.py` each define their own `@lru_cache` factories independently; they do not share singletons. `handler_narrative.py` reuses `app/dependencies.py` factories.

**SSM secret indirection (`app/config.py`):** env vars for secrets (OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_HOST) are set to SSM parameter paths in Lambda (e.g. `/you-api/openai-api-key`). At runtime `get_secret()` detects a leading `/` and fetches+decrypts from SSM. Locally, set these to raw values.

**`handler_embedding.py` has no in-memory fallback** — unlike `dependencies.py`, it always uses `OpenAIEmbeddingClient` and `PineconeVectorRepository` regardless of env vars. Only `TAG_EXTRACTION_TYPE` is switchable there. Do not expect the in-memory adapters to work for the embedding pipeline.

**DynamoDB Streams only on the prod table** (`entries`). The test table (`test_entries`) has no stream, so the embedding Lambda never fires locally or in tests.

**Production failure path:** embedding Lambda failures land in an SQS DLQ (`EmbeddingDLQ`). A CloudWatch alarm fires when the DLQ has ≥ 1 message and sends an SNS email alert. Check the DLQ first when tags stop appearing on new entries.

**Authentication:** API Gateway Cognito authorizer validates JWTs. `get_current_user_id(request)` extracts `sub` from `event["requestContext"]["authorizer"]["claims"]["sub"]`. Falls back to `DEV_USER_ID` env var locally. User ID is never accepted from request bodies.

**Route ordering in `app/routers/entries.py`:** `GET /summary` and `GET /narrative` must be declared before `GET /{entry_id}`. FastAPI matches top-to-bottom; the literal path segments would otherwise be captured as `entry_id` values.

**`narrative_repository.py` deviates from the pattern:** It contains both the ABC and `DynamoDBNarrativeRepository` in the same file. Every other repository keeps the DynamoDB impl in a separate `dynamodb_*.py` file. `InMemoryNarrativeRepository` follows the standard separate-file pattern.

**`app/embedding/embedding_port.py` is dead code** — an identical ABC exists in `embedding_client.py`. All production code imports from `embedding_client.py`; `embedding_port.py` is a leftover from an earlier refactor.

## Conventions

- No comments on obvious code
- Repository pattern for all data access
- Keep route handlers thin — logic belongs in services
- `@lru_cache` singletons: tests that swap env vars must call `cache_clear()` on each factory in an `autouse` fixture — see `tests/test_dependencies.py`
- Router tests use `app.dependency_overrides` to inject fakes for `get_service` and `get_current_user_id`; clear overrides in fixture teardown
- Coverage minimum is 80% (`--cov-fail-under=80`), measured over `app/` only