# you-api

FastAPI + AWS Lambda + DynamoDB entries API.

## Stack

- Python 3.13, FastAPI, Mangum (Lambda adapter), boto3, Pydantic v2
- Infrastructure: AWS CDK (Python) in `infra/`
- Package manager: `uv`

## Run

```bash
make run-mem      # in-memory (no AWS)
make run          # DynamoDB test table
make run-prod     # DynamoDB prod table
```

## Deploy

```bash
make requirements          # regenerate app/requirements.txt
cd infra && cdk deploy --all
```

## Architecture

Routes → Service → Repository (ABC). Two implementations: `InMemoryEntryRepository` (local) and `DynamoDBEntryRepository` (prod). Selected via `REPOSITORY_TYPE` env var; singleton via `@lru_cache`.

## Conventions

- No comments on obvious code
- Repository pattern for all data access
- Keep route handlers thin — logic belongs in services