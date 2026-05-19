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
make run-mem           # in-memory (no AWS)
make run               # DynamoDB test table
make run-prod          # DynamoDB prod table
make requirements      # regenerate app/requirements.txt for Lambda packaging

uv run pytest          # run all tests
uv run pytest tests/test_entry_service.py::test_name  # single test

cd infra && cdk deploy --all
```

## Architecture

**Two Lambda functions:**
- `handler.py` — wraps FastAPI via Mangum; handles all HTTP CRUD
- `handler_embedding.py` — DynamoDB Streams consumer; embeds new entries async via OpenAI → Pinecone

**Write path is non-blocking:** entries are saved to DynamoDB first; embeddings happen in the background via Streams.

**Adapters behind ABCs, selected by env vars at startup, singletons via `@lru_cache`:**
- `REPOSITORY_TYPE=dynamodb` → `DynamoDBEntryRepository`, else `InMemoryEntryRepository`
- `EMBEDDING_TYPE=openai` → `OpenAIEmbeddingClient`, else `InMemoryEmbeddingClient`
- `VECTOR_REPOSITORY_TYPE=pinecone` → `PineconeVectorRepository`, else `InMemoryVectorRepository`

**Authentication:** API Gateway Cognito authorizer validates JWTs. `get_current_user_id(request)` extracts `sub` from `event["requestContext"]["authorizer"]["claims"]["sub"]`. Falls back to `DEV_USER_ID` env var locally. User ID is never accepted from request bodies.

## Conventions

- No comments on obvious code
- Repository pattern for all data access
- Keep route handlers thin — logic belongs in services