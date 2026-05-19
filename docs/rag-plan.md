# RAG Implementation Plan — Semantic Search

Add vector embeddings to diary entries and expose a semantic search endpoint.
Embedding generation is async (DynamoDB Streams → Lambda), decoupled from the CRUD API.
Pinecone is the vector store, hidden behind an interface for easy replacement.
OpenAI `text-embedding-3-small` handles both Ukrainian and English entries.
Entry date is embedded with the text to support time-aware queries.

---

## Architecture

```
POST /entries
  └── save to DynamoDB → return 201 immediately

DynamoDB Stream (INSERT event)
  └── embedding-processor Lambda
        ├── build text: "Date: {timestamp}\n\n{entry_text}"
        ├── call EmbeddingPort.embed(text)
        └── VectorRepository.upsert(entry_id, user_id, vector)

POST /entries/search { query }
  └── EmbeddingPort.embed(query)
  └── VectorRepository.search(user_id, top_k=10) → entry_ids
  └── DynamoDB get by entry_ids
  └── return { entries: [...] }
```

---

## New abstractions

**`app/ports/embedding_port.py`** — `EmbeddingPort` ABC
- `embed(text: str) -> list[float]`
- Impls: `OpenAIEmbeddingClient` (prod), `InMemoryEmbeddingClient` (tests)

**`app/repositories/vector_repository.py`** — `VectorRepository` ABC
- `upsert(entry_id, user_id, vector) -> None`
- `search(user_id, vector, top_k=10) -> list[str]`
- Impls: `PineconeVectorRepository` (prod), `InMemoryVectorRepository` (local/tests)

---

## New files

```
app/ports/__init__.py
app/ports/embedding_port.py
app/ports/openai_embedding_client.py
app/ports/in_memory_embedding_client.py
app/repositories/vector_repository.py
app/repositories/in_memory_vector_repository.py
app/repositories/pinecone_vector_repository.py
app/handler_embedding.py                 ← stream processor Lambda entry point
scripts/setup_pinecone.py                ← one-time index creation
```

## Modified files

```
pyproject.toml                           ← add openai>=1.30, pinecone>=5.0
app/models/entry.py                      ← add SearchRequest, SearchResult
app/services/entry_service.py            ← add search_entries()
app/dependencies.py                      ← add _embedding_port(), _vector_repository()
app/routers/entries.py                   ← add POST /entries/search (before /{entry_id})
infra/stacks/dynamodb_stack.py           ← enable Streams (NEW_IMAGE)
infra/stacks/api_stack.py               ← embedding Lambda + event source + env vars
```

---

## Env vars

| Var | Used by |
|---|---|
| `OPENAI_API_KEY` | both Lambdas |
| `PINECONE_API_KEY` | both Lambdas |
| `PINECONE_INDEX_HOST` | both Lambdas (from setup_pinecone.py output) |
| `PINECONE_INDEX_NAME` | setup script (`you-entries`) |
| `VECTOR_REPOSITORY_TYPE` | API Lambda (`pinecone` / `in_memory`) |

---

## Pinecone index setup (one-time)

```bash
PINECONE_API_KEY=xxx python scripts/setup_pinecone.py
# copy printed host URL → PINECONE_INDEX_HOST env var
```

Index: serverless, AWS us-east-1, cosine metric, 1536 dims.

---

## Implementation order

```
1.  scripts/setup_pinecone.py
2.  pyproject.toml
3.  app/ports/embedding_port.py
4.  app/ports/openai_embedding_client.py
5.  app/ports/in_memory_embedding_client.py
6.  app/repositories/vector_repository.py
7.  app/repositories/in_memory_vector_repository.py
8.  app/repositories/pinecone_vector_repository.py
9.  app/models/entry.py
10. app/services/entry_service.py
11. app/dependencies.py
12. app/routers/entries.py
13. app/handler_embedding.py
14. infra/stacks/dynamodb_stack.py
15. infra/stacks/api_stack.py
```