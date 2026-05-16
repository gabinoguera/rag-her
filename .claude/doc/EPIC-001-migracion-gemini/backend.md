# EPIC-001: Migración del Núcleo RAG a Gemini — Backend Implementation Plan

**Feature:** EPIC-001-migracion-gemini
**Date:** 2026-05-16
**Author:** @backend-developer
**Stack:** FastAPI, SQLAlchemy async, Python 3.11, PostgreSQL+pgvector, pytest-asyncio, google-genai>=2.3.0

---

## Overview

This plan covers all backend changes needed to replace OpenAI with Google Gemini (google-genai SDK),
reduce embedding dimensions from 1536 to 768, simplify the retrieval re-ranking logic, and delete
all legacy estimation modules. No Alembic migration is required in this epic — the dimension change
on the `rag.chunks` table is deferred to EPIC-002 where new tables will be created from scratch.

---

## RAG-01 — app/config.py

### Settings to Remove

```python
OPENAI_API_KEY: str = ""
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: int = 1536
LLM_MODEL: str = "o4-mini"
LLM_MAX_OUTPUT_TOKENS: int = 16384
LLM_TIMEOUT: int = 120
```

### Settings to Add

```python
# Gemini
GEMINI_API_KEY: str = ""
EMBEDDING_MODEL: str = "text-multilingual-embedding-002"
EMBEDDING_DIMENSIONS: int = 768
LLM_MODEL: str = "gemini-2.5-flash"
LLM_MAX_OUTPUT_TOKENS: int = 8192
```

Note: `LLM_TIMEOUT` is dropped entirely. The `google-genai` SDK does not expose a global timeout
the same way `AsyncOpenAI` does. Timeout is handled via retry logic in `generation.py`.

### Updated Validator

The existing `embedding_dimensions_must_be_positive` validator on `EMBEDDING_DIMENSIONS` is correct
as-is (checks `v <= 0`). Add an explicit allowed-values check to guard against accidental misconfiguration:

```python
@field_validator("EMBEDDING_DIMENSIONS")
@classmethod
def embedding_dimensions_must_be_valid(cls, v: int) -> int:
    if v <= 0:
        raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer")
    allowed = {768, 1536}
    if v not in allowed:
        raise ValueError(f"EMBEDDING_DIMENSIONS must be one of {allowed}, got {v}")
    return v
```

This is intentionally strict: during the migration window only 768 is valid for new data,
but 1536 is kept in the allowed set so that any dev who reads existing data is not broken at config
load time (relevant until EPIC-002 completes the table migration).

### .env.example changes

Add:
```
GEMINI_API_KEY=your-gemini-api-key-here
```

Remove:
```
OPENAI_API_KEY=...
```

---

## RAG-02 — app/core/embeddings.py

### Key Design Decisions

1. `google-genai` SDK (`genai.Client`) is synchronous at the call level but the method
   `client.models.embed_content(...)` is blocking. The existing service is `async` because it
   was wrapping `AsyncOpenAI`. The new implementation must wrap the synchronous `genai` call with
   `asyncio.get_event_loop().run_in_executor(None, ...)` OR use a thread pool to keep the public
   `async` interface unchanged without blocking the FastAPI event loop.

   Recommended approach: use `asyncio.to_thread()` (Python 3.9+, available in 3.11) to call the
   synchronous `client.models.embed_content` in a thread pool:

   ```python
   import asyncio
   result = await asyncio.to_thread(
       client.models.embed_content,
       model=self._model,
       contents=text,
       config=EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768),
   )
   ```

2. Batch embedding: the Gemini embedding API accepts a single string per call (unlike OpenAI
   which accepts a list). For `generate_embeddings(texts: list[str])`, iterate and call per text,
   OR use `asyncio.gather()` for concurrent calls.
   Use `asyncio.gather()` for parallelism with individual calls — more efficient than sequential.

3. Remove `tiktoken` entirely. Gemini does not require manual token truncation for embeddings.
   If texts are too long the API will return an error — catch and wrap in `EmbeddingError`.

4. Keep `EmbeddingError` exception class unchanged.

5. Keep public signatures unchanged:
   - `async def generate_embeddings(texts: list[str]) -> list[list[float]]`
   - `async def generate_single_embedding(text: str) -> list[float]`

### New EmbeddingService Constructor

```python
class EmbeddingService:
    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dimensions = dimensions
```

The `genai.Client` instance is created once per service instance. The dependency factory in
`app/dependencies.py` creates a new `EmbeddingService` per request (via `Depends`), so consider
making the client a module-level singleton to avoid re-initializing on each request.
For EPIC-001 scope, keep the per-request construction to match existing behavior.

### Error Mapping

Map `google.api_core.exceptions` to `EmbeddingError`:

| google exception | maps to |
|---|---|
| `google.api_core.exceptions.Unauthenticated` | `EmbeddingError("Authentication failed: ...")` |
| `google.api_core.exceptions.ResourceExhausted` | `EmbeddingError("Rate limit exceeded: ...")` |
| `google.api_core.exceptions.GoogleAPICallError` (base) | `EmbeddingError("API error: ...")` |
| Any other `Exception` | re-raise as `EmbeddingError("Unexpected error: ...")` |

### Import changes

Remove:
```python
import tiktoken
from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError
```

Add:
```python
import asyncio
import google.api_core.exceptions
import google.genai as genai
from google.genai.types import EmbedContentConfig
```

---

## RAG-03 — app/core/generation.py

### Key Design Decisions

1. Replace `AsyncOpenAI` with `genai.Client`. Like embeddings, `client.models.generate_content()`
   is synchronous. Wrap with `asyncio.to_thread()`.

2. Simplify to a single public method:
   ```python
   async def generate(
       self,
       prompt: str,
       system_instruction: str | None = None,
   ) -> str:
   ```
   Remove `generate_estimation()`, `validate_estimation()`, `build_fallback_estimation()`,
   `_call_llm_with_retries()`, `_call_llm()`. These were tied to the now-deleted estimation pipeline.

3. New constructor:
   ```python
   class GenerationService:
       def __init__(self, api_key: str, model: str, max_output_tokens: int = 8192) -> None:
           self._client = genai.Client(api_key=api_key)
           self._model = model
           self._max_output_tokens = max_output_tokens
   ```
   No `timeout` parameter — dropped in RAG-01.

4. Retry logic (replaces the OpenAI retry strategy):

   | Exception | Strategy |
   |---|---|
   | `google.api_core.exceptions.ResourceExhausted` | Exponential backoff: 2s→4s→8s→16s, max 4 retries |
   | `google.api_core.exceptions.DeadlineExceeded` | 1 retry immediately |
   | `google.api_core.exceptions.Unauthenticated` | Fail immediately (raise `GenerationError`) |
   | `google.api_core.exceptions.GoogleAPICallError` | Fail immediately (raise `GenerationError`) |

5. The `generate()` method uses `GenerateContentConfig`:
   ```python
   from google.genai.types import GenerateContentConfig, Part, Content

   config = GenerateContentConfig(
       max_output_tokens=self._max_output_tokens,
       system_instruction=system_instruction,
   )
   response = await asyncio.to_thread(
       self._client.models.generate_content,
       model=self._model,
       contents=prompt,
       config=config,
   )
   ```

6. Empty response guard: if `response.text` is empty/None, raise `GenerationError("Empty response")`.

7. Keep `GenerationError` exception class unchanged.

### Import changes

Remove:
```python
from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError
from app.core.prompt_builder import ...
from app.core.response_parser import ...
```

Add:
```python
import asyncio
import google.api_core.exceptions
import google.genai as genai
from google.genai.types import GenerateContentConfig
```

### CORRECTION_PROMPT constant

Remove `CORRECTION_PROMPT` (was coupled to estimation JSON schema). If needed by future callers,
move to `app/core/prompts.py`.

---

## RAG-04 — app/core/retrieval.py

### SQL Changes

The `<=>` cosine distance operator works for any dimension — no SQL operator change needed.
The dimension change is implicit once the `rag.chunks.embedding` column is migrated to `Vector(768)`
in EPIC-002. For EPIC-001, the SQL itself needs no dimension-specific changes.

Remove the legacy filter clauses from `search()`:

1. Remove `chunk_types` filter block (lines 94–96 in current file).
2. Remove `technologies` filter block (lines 98–100).
3. Remove `min_cost` / `max_cost` filter blocks (lines 102–108).

The `where_clauses` after cleanup should only contain:
```python
where_clauses = [
    "c.embedding IS NOT NULL",
    "1 - (c.embedding <=> :query_embedding) >= :min_similarity",
]
```

Remove from `params`: `chunk_types`, `technologies`, `min_cost`, `max_cost`.

### Re-ranking Changes

Replace the 4-component score call:
```python
# OLD
tech_score = technology_match_score(row.technologies, preprocessed.detected_technologies)
rec_score = recency_score(row.created_at, now)
cost_score = cost_range_score(row.total_cost, all_costs)
final = calculate_final_score(row.similarity, tech_score, rec_score, cost_score)
```

With the 2-component call:
```python
# NEW
rec_score = recency_score(row.created_at, now)
final = calculate_final_score(row.similarity, rec_score)
```

Remove `all_costs` computation (no longer needed).

### Removed imports from retrieval.py

Remove:
```python
from app.core.query_preprocessing import preprocess_query
from app.core.ranking import (
    cost_range_score,
    technology_match_score,
    ...
)
from app.models.search_log import SearchLog
```

Keep:
```python
from app.core.ranking import ScoredResult, calculate_final_score, deduplicate_results, recency_score
```

### SearchLog removal

The `SearchLog` model is in the deletion list (RAG-05). Remove the logging block from `search()`:
lines 170–190 in current file (the `try: search_log = SearchLog(...)` block).

### Simplified ScoredResult fields

`ScoredResult` in `app/core/ranking.py` should drop legacy fields:
- Remove: `chunk_type`, `document_id`, `technologies`, `total_cost`, `currency`
- Keep: `chunk_id`, `content_text`, `metadata`, `project_title`, `created_at`, `similarity_score`, `final_score`

Note: `chunk_type` appears in `SearchResultItem` (search response schema). If `app/api/v1/search.py`
still exposes `chunk_type` in the response, keep `chunk_type` on `ScoredResult` but remove all others.
Decision: keep `chunk_type` and `document_id` on `ScoredResult` to avoid breaking `SearchResultItem`
schema. Remove only: `technologies`, `total_cost`, `currency`.

### Remove search_for_task method

`search_for_task()` used `chunk_types=["line_item"]` filter. With filters removed, this method
either delegates to plain `search()` or is deleted. Since `search_for_task()` was called only from
`EstimationPipeline` (being deleted in RAG-05), delete this method entirely.

### query_preprocessing dependency

`preprocess_query` from `app/core/query_preprocessing.py` is in the deletion list. Replace usage
in `retrieval.py` with a trivial inline substitute:

```python
# BEFORE
preprocessed = preprocess_query(request.query)
query_embedding = await self._embedding_service.generate_single_embedding(
    preprocessed.processed_text
)
```

```python
# AFTER
query_embedding = await self._embedding_service.generate_single_embedding(request.query)
```

Remove all references to `preprocessed.detected_technologies` and `preprocessed.suggested_chunk_types`
from the `SearchResponse` construction. Update `SearchResponse` schema to remove these optional fields
or keep them as empty lists.

Note: Check `app/api/schemas/search_response.py` — if `detected_technologies` and `suggested_chunk_types`
are required response fields, set them to `[]` (empty list) in the new implementation.

---

## RAG-05 — app/core/ranking.py Changes

### calculate_final_score signature change

```python
# OLD
def calculate_final_score(
    similarity: float,
    tech_match: float,
    recency: float,
    cost_range: float,
) -> float:
    return 0.50 * similarity + 0.25 * tech_match + 0.15 * recency + 0.10 * cost_range

# NEW
def calculate_final_score(similarity: float, recency: float) -> float:
    return 0.70 * similarity + 0.30 * recency
```

### Functions to remove from ranking.py

- `technology_match_score()` — remove entirely
- `cost_range_score()` — remove entirely

### Functions to keep

- `recency_score()` — keep unchanged (formula and signature unchanged)
- `deduplicate_results()` — keep, but update `ScoredResult` field usage if fields are removed
- `calculate_final_score()` — update signature as shown above

---

## RAG-05 — Files to Delete

### app/core/ (10 files)

```
app/core/chunking.py
app/core/quote_generation_pipeline.py
app/core/query_preprocessing.py
app/core/reasoning_service.py
app/core/prompt_builder.py
app/core/quote_prompt_builder.py
app/core/pipeline.py
app/core/response_parser.py
app/core/anonymization.py
app/core/confidence.py
```

### app/api/v1/ (4 files)

```
app/api/v1/estimate.py
app/api/v1/quote_generator.py
app/api/v1/ingest.py
app/api/v1/stats.py
```

### app/models/ (4 files)

```
app/models/document.py
app/models/ingestion_log.py
app/models/search_log.py
app/models/chunk.py
```

**Important note on model deletions:** `app/models/chunk.py` contains the `Chunk` SQLAlchemy model
which is imported by `tests/test_models/test_vector_search.py` and `tests/test_api/test_search.py`
(via ingest). In EPIC-001 the `rag.chunks` table still exists in the DB (the embedding column
still has 1536 dims until EPIC-002). The `Chunk` model is being deleted because it references
`Vector(1536)` which will become stale. If the search endpoint still reads from `rag.chunks`,
the model cannot be fully deleted — it must at minimum have its `Vector(1536)` updated.

Decision for EPIC-001: **do not delete `app/models/chunk.py`**. Instead, defer this deletion
to EPIC-002 alongside the Alembic migration. Update the issue appendix accordingly.
The `chunk.py` model stays but `document.py`, `ingestion_log.py`, `search_log.py` are deleted.

### app/services/ (1 file)

```
app/services/ingest_service.py
```

### app/api/schemas/ (files to clean or delete)

The following schema files become unused after deleting the estimate/ingest/quote routes:
```
app/api/schemas/estimate_request.py    (delete)
app/api/schemas/estimate_response.py   (delete)
app/api/schemas/ingest_response.py     (delete)
app/api/schemas/quote_generation.py    (delete)
app/api/schemas/quote_input.py         (delete)
app/api/schemas/quote_output.py        (delete)
app/api/schemas/transcription_analysis.py  (delete)
```

Keep:
```
app/api/schemas/common.py
app/api/schemas/search_request.py
app/api/schemas/search_response.py
```

---

## RAG-06 — app/api/v1/router.py

### New router.py content

```python
from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.search import router as search_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(search_router, tags=["search"])
```

Remove imports and `include_router` calls for: `ingest_router`, `estimate_router`,
`stats_router`, `quote_generator_router`.

---

## RAG-07 — app/main.py

`app/main.py` itself needs minimal changes — it imports only from `app/api/v1/router` which is
already being updated. However, verify there are no direct imports of deleted modules.

Current `main.py` imports: `app.api.v1.router`, `app.config`, `app.db`, `app.utils.logging`.
None of these are in the deletion list, so `main.py` requires no changes beyond confirming
the lifespan log fields match the new settings:

```python
# Line 32 in current main.py — this still works because settings.EMBEDDING_MODEL and
# settings.LLM_MODEL are still present (just with new values)
embedding_model=settings.EMBEDDING_MODEL,
llm_model=settings.LLM_MODEL,
```

---

## RAG-08 — app/dependencies.py

### Functions to remove

- `get_generation_service()` — remove (keep for now only if `search.py` uses it; it does not)
- `get_ingest_service()` — remove
- `get_estimation_pipeline()` — remove
- `get_reasoning_service()` — remove
- `get_quote_generation_pipeline()` — remove

### get_embedding_service() changes

```python
# OLD
def get_embedding_service(settings: Settings = Depends(get_settings)) -> EmbeddingService:
    return EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )

# NEW
def get_embedding_service(settings: Settings = Depends(get_settings)) -> EmbeddingService:
    return EmbeddingService(
        api_key=settings.GEMINI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
```

### Functions to keep

- `get_current_settings()`
- `get_db_session()`
- `get_embedding_service()` (updated as above)
- `get_retrieval_service()`

---

## RAG-09 — pyproject.toml

### Dependencies to remove

```toml
"openai>=1.0",
"tiktoken>=0.7",
```

### Dependencies to add

```toml
"google-genai>=2.3.0",
```

The `google-genai` package includes `google-api-core` as a transitive dependency which provides
`google.api_core.exceptions` (used in error handling for both embeddings and generation).

---

## RAG-10 — tests/conftest.py

### get_test_settings() changes

```python
# OLD
def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=DATABASE_URL,
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
        API_KEY="test-api-key",
        OPENAI_API_KEY="test-key",
    )

# NEW
def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=DATABASE_URL,
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
        API_KEY="test-api-key",
        GEMINI_API_KEY="test-gemini-key",
    )
```

### _make_mock_embedding_service() changes

```python
# OLD
async def mock_generate(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]

service.generate_single_embedding = AsyncMock(
    side_effect=lambda text: [0.1] * 1536
)

# NEW
async def mock_generate(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 768 for _ in texts]

service.generate_single_embedding = AsyncMock(
    side_effect=lambda text: [0.1] * 768
)
```

### _make_mock_generation_service() changes

This function references `LLMEstimationResponse` from `app.core.response_parser` (being deleted).
Remove `_make_mock_generation_service()` entirely and the `client_with_mock_llm` fixture.

Also remove references in `client_with_mock_llm` fixture to:
- `get_generation_service` dependency override
- Tables: `rag.search_logs`, `rag.ingestion_logs`, `rag.chunks`, `rag.documents`

The `client_with_mock_embeddings` fixture's table cleanup block also references deleted tables.
After RAG-05, only `rag.chunks` remains (documents table is deleted too if `document.py` model
is removed). Re-evaluate which tables to clean given the new schema.

### live_api fixture

Update the `--live-api` option help text:
```python
# OLD
help="Run tests that call live external APIs (OpenAI)",

# NEW
help="Run tests that call live external APIs (Gemini)",
```

---

## Tests to Delete

```
tests/test_core/test_chunking.py
tests/test_core/test_query_preprocessing.py
tests/test_core/test_pipeline.py
tests/test_core/test_prompt_builder.py
tests/test_core/test_response_parser.py
tests/test_core/test_anonymization.py
tests/test_core/test_confidence.py
tests/test_api/test_estimate.py
tests/test_api/test_ingest.py
tests/test_api/test_stats.py
tests/test_api/schemas/test_quote_validation.py
tests/test_models/test_chunk.py
tests/test_models/test_document.py
```

---

## Tests to Rewrite

### tests/test_core/test_embeddings.py

Full rewrite. Key changes:

1. `_make_service()` no longer needs `dimensions=1536` — change to `dimensions=768`.
2. `_make_mock_response()` is replaced. The new `EmbeddingService` calls `genai.Client` which
   returns a `google.genai.types.EmbedContentResponse`. Mock the `client.models.embed_content`
   synchronous method (which is now wrapped in `asyncio.to_thread`):

   ```python
   def _make_service(mock_embed_fn=None) -> EmbeddingService:
       service = EmbeddingService(api_key="test-key", model="test-model", dimensions=768)
       if mock_embed_fn is not None:
           service._client = MagicMock()
           service._client.models.embed_content = mock_embed_fn
       return service
   ```

   Since `embed_content` is called via `asyncio.to_thread()`, mock it as a regular synchronous
   `MagicMock` (not `AsyncMock`):

   ```python
   mock_response = MagicMock()
   mock_response.embeddings = [MagicMock(values=[0.1] * 768)]
   service._client.models.embed_content = MagicMock(return_value=mock_response)
   ```

   Note: the actual `EmbedContentResponse` structure from `google-genai` SDK:
   - Single text call: `response.embeddings[0].values` is the float list
   - Access pattern: `result.embeddings[0].values`

3. Error tests: replace `openai.AuthenticationError`, `openai.RateLimitError`, `openai.APIError`
   with `google.api_core.exceptions.Unauthenticated`, `google.api_core.exceptions.ResourceExhausted`,
   `google.api_core.exceptions.GoogleAPICallError`.

4. Remove `TestEmbeddingValidation.test_wrong_dimensions_raises` test that used `[0.1] * 768`
   as "wrong" — now 768 is correct. Add a test with `[0.1] * 1536` as wrong dimensions instead
   (or parameterize).

5. All dimension assertions change from 1536 to 768.

### tests/test_core/test_ranking.py

Partial rewrite. Key changes:

1. `TestCalculateFinalScore.test_weights_are_correct`:
   ```python
   # OLD: tests 4 parameters with old weights
   # NEW: tests 2 parameters with new weights
   def test_weights_are_correct(self) -> None:
       # Only similarity=1.0, recency=0.0
       score = calculate_final_score(similarity=1.0, recency=0.0)
       assert abs(score - 0.70) < 1e-9

       # Only recency=1.0, similarity=0.0
       score = calculate_final_score(similarity=0.0, recency=1.0)
       assert abs(score - 0.30) < 1e-9
   ```

2. Remove import and tests for `technology_match_score` and `cost_range_score`.

3. `TestDeduplicateResults._make_result()` — `ScoredResult` will have fewer fields after cleanup.
   Update constructor call to not pass `technologies`, `total_cost`, `currency` if removed.

4. `calculate_final_score` call in `_make_result` or `final_score` parameter must be updated.

### tests/test_models/test_vector_search.py

Rewrite to use 768-dim vectors:

```python
# OLD
base_vector = [1.0] + [0.0] * 1535
similar_vector = [0.9] + [0.1] + [0.0] * 1534
different_vector = [0.0] + [1.0] + [0.0] * 1534
opposite_vector = [-1.0] + [0.0] * 1535

wrong_dims_vector = [0.1] * 100  # keep as wrong dims test
```

```python
# NEW
base_vector = [1.0] + [0.0] * 767
similar_vector = [0.9] + [0.1] + [0.0] * 766
different_vector = [0.0] + [1.0] + [0.0] * 766
opposite_vector = [-1.0] + [0.0] * 767

wrong_dims_vector = [0.1] * 100  # still wrong, keep as-is
```

Note: This test will fail until EPIC-002 migrates the `rag.chunks.embedding` column to `Vector(768)`.
Mark these tests with `@pytest.mark.skip(reason="Requires EPIC-002 schema migration")` for EPIC-001
execution, and remove the skip marker in EPIC-002.

### tests/test_api/test_search.py

Partial rewrite. Key changes:

1. Remove `_ingest_full_quote()` helper and all tests that call `/api/v1/ingest`
   (since the ingest endpoint is deleted). Replace with direct DB insertion fixtures.

2. Remove tests that rely on `search_log` / stats endpoint:
   - `test_search_logging_recorded` — delete (stats endpoint removed).

3. Remove test `test_search_filter_by_chunk_type` and `test_search_filter_by_technologies`
   since these filters are removed from the API (if `SearchFilters` schema is cleaned up).

4. Update mock embedding service to 768 dims in `conftest.py` (already covered above).

---

## MoSCoW Priority Table

| Priority | Capability | Rationale |
|----------|-----------|-----------|
| Must | Replace `OPENAI_API_KEY` with `GEMINI_API_KEY` in `app/config.py` | All downstream AI calls fail without this |
| Must | Rewrite `app/core/embeddings.py` using `genai.Client` with 768d | Blocks EPIC-002 new table creation |
| Must | Rewrite `app/core/generation.py` using `gemini-2.5-flash` | Required for all future conversational features |
| Must | Update `app/core/ranking.py`: new 2-weight `calculate_final_score(similarity, recency)` | Search quality depends on correct weights |
| Must | Simplify `app/core/retrieval.py`: remove legacy filters, query_preprocessing dep | Prevents import errors after module deletions |
| Must | Update `app/api/v1/router.py` to expose only `health` and `search` routes | Prevents 404 errors on previously valid routes from being silent |
| Must | Delete 18 legacy files and their imports | Eliminates dead code that creates confusion and import chains |
| Must | Update `pyproject.toml`: remove `openai`, `tiktoken`; add `google-genai>=2.3.0` | Dependency correctness |
| Must | Update `tests/conftest.py`: 768d mocks, `GEMINI_API_KEY` in test settings | Tests are broken without this |
| Should | Rewrite `tests/test_core/test_embeddings.py` with Gemini mock patterns | CI must pass |
| Should | Rewrite `tests/test_core/test_ranking.py` for new 2-weight signature | CI must pass |
| Should | Update `tests/test_models/test_vector_search.py` vectors to 768d | Prevents dimension mismatch errors |
| Should | Update `app/dependencies.py`: use `GEMINI_API_KEY`, remove deleted service factories | Prevents dependency injection errors at startup |
| Could | Add `genai.Client` singleton (module-level) to avoid per-request re-initialization | Performance optimization, deferred to EPIC-002+ |
| Could | Add `@pytest.mark.skip` on vector search tests pending EPIC-002 migration | Clean test output |
| Won't | Alembic migration for `rag.chunks.embedding` `Vector(1536)` → `Vector(768)` | Deferred to EPIC-002 (new tables, not migration) |
| Won't | Remove `app/models/chunk.py` in EPIC-001 | The search endpoint still reads from `rag.chunks`; deletion is EPIC-002 scope |
| Won't | Add rate-limit circuit breaker (token bucket, persistent backoff state) | EPIC-001 scope is replacement parity, not enhancement |
| Won't | Prometheus metrics for Gemini latency / token usage | Out of scope for migration epic |

---

## Implementation Phases

| # | Phase | File(s) | Description | TDD | Parallel | Depends |
|---|-------|---------|-------------|-----|----------|---------|
| 1 | RAG-01: Config update | `app/config.py`, `.env.example` | Remove OpenAI settings, add GEMINI_API_KEY, update EMBEDDING_DIMENSIONS default to 768, update validator | Yes | — | — |
| 2 | RAG-01: Dependencies update | `pyproject.toml` | Remove `openai`, `tiktoken`; add `google-genai>=2.3.0` | No | Parallel with phase 1 | — |
| 3 | RAG-02: Embeddings rewrite | `app/core/embeddings.py` | New `EmbeddingService` using `genai.Client`, `asyncio.to_thread`, `EmbedContentConfig`, new error mapping | Yes | Parallel with phase 4 | Phase 1, 2 |
| 4 | RAG-03: Generation rewrite | `app/core/generation.py` | New `GenerationService.generate()` using `gemini-2.5-flash`, new retry strategy for `ResourceExhausted`/`DeadlineExceeded` | Yes | Parallel with phase 3 | Phase 1, 2 |
| 5 | RAG-05: Delete legacy modules | `app/core/{chunking,quote_generation_pipeline,query_preprocessing,reasoning_service,prompt_builder,quote_prompt_builder,pipeline,response_parser,anonymization,confidence}.py` | Delete 10 core modules | No | Parallel with phase 3, 4 | Phase 1 |
| 6 | RAG-05: Delete legacy API routes | `app/api/v1/{estimate,quote_generator,ingest,stats}.py` | Delete 4 API route files | No | Parallel with phase 5 | Phase 1 |
| 7 | RAG-05: Delete legacy models | `app/models/{document,ingestion_log,search_log}.py` (NOT chunk.py) | Delete 3 model files | No | Parallel with phase 5, 6 | Phase 1 |
| 8 | RAG-05: Delete legacy schemas | `app/api/schemas/{estimate_request,estimate_response,ingest_response,quote_generation,quote_input,quote_output,transcription_analysis}.py` | Delete 7 schema files | No | Parallel with phase 5, 6, 7 | Phase 1 |
| 9 | RAG-05: Delete legacy services | `app/services/ingest_service.py` | Delete ingest service | No | Parallel with phase 5–8 | Phase 1 |
| 10 | RAG-05: Delete legacy tests | `tests/test_core/{test_chunking,test_query_preprocessing,test_pipeline,test_prompt_builder,test_response_parser,test_anonymization,test_confidence}.py`, `tests/test_api/{test_estimate,test_ingest,test_stats}.py`, `tests/test_api/schemas/test_quote_validation.py`, `tests/test_models/{test_chunk,test_document}.py` | Delete 13 test files | No | Parallel with phase 5–9 | Phase 1 |
| 11 | RAG-06: Router cleanup | `app/api/v1/router.py` | Keep only health + search routes | No | — | Phase 6 |
| 12 | RAG-07: dependencies.py cleanup | `app/dependencies.py` | Update `get_embedding_service` to use `GEMINI_API_KEY`; remove factory functions for deleted services | No | Parallel with phase 11 | Phase 3, 5, 6, 7 |
| 13 | RAG-04: Retrieval simplification | `app/core/retrieval.py` | Remove legacy filters from SQL, remove `query_preprocessing` call, remove `SearchLog` logging block, update re-ranking call | Yes | — | Phase 3, 5, 7 |
| 14 | RAG-04: Ranking simplification | `app/core/ranking.py` | New `calculate_final_score(similarity, recency)` signature with 0.70/0.30 weights; remove `technology_match_score`, `cost_range_score`; slim `ScoredResult` dataclass | Yes | Parallel with phase 13 | Phase 5 |
| 15 | Test rewrites: conftest | `tests/conftest.py` | Update `get_test_settings` (GEMINI_API_KEY), `_make_mock_embedding_service` (768d), remove `_make_mock_generation_service`, `client_with_mock_llm` fixture | Yes | — | Phase 1, 10 |
| 16 | Test rewrites: embeddings | `tests/test_core/test_embeddings.py` | Full rewrite: Gemini mock patterns, 768d, new error types | Yes | Parallel with phase 17, 18 | Phase 3, 15 |
| 17 | Test rewrites: ranking | `tests/test_core/test_ranking.py` | Update `calculate_final_score` tests for 2-weight signature; remove `technology_match_score`/`cost_range_score` tests | Yes | Parallel with phase 16, 18 | Phase 14 |
| 18 | Test rewrites: vector_search | `tests/test_models/test_vector_search.py` | Update vectors to 768d; add skip markers pending EPIC-002 | Yes | Parallel with phase 16, 17 | Phase 15 |
| 19 | Test rewrites: search API | `tests/test_api/test_search.py` | Remove ingest dependency; remove stats/filter tests; keep core search behavior tests | Yes | — | Phase 11, 13, 15 |
| 20 | Integration verification | All | `pytest -x` green; no import of `openai`/`tiktoken` anywhere in `app/`; `ruff check app/` clean | No | — | All phases |

---

## Important Notes for Implementors

### google-genai SDK version compatibility

As of `google-genai>=2.3.0`, the embedding API call is:

```python
from google import genai
from google.genai.types import EmbedContentConfig

client = genai.Client(api_key="...")

# Single text embedding
response = client.models.embed_content(
    model="text-multilingual-embedding-002",
    contents="your text here",
    config=EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=768,
    ),
)
embedding_values: list[float] = response.embeddings[0].values
```

For generation:
```python
from google.genai.types import GenerateContentConfig

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="your prompt here",
    config=GenerateContentConfig(
        system_instruction="your system instruction",
        max_output_tokens=8192,
    ),
)
text: str = response.text
```

Both `embed_content` and `generate_content` are **synchronous** in `google-genai>=2.3.0`.
The async variants (`aio.models.embed_content`, `aio.models.generate_content`) exist via
`client.aio.models.*` in newer versions. Verify availability before using the async path;
if available, prefer it to avoid the `asyncio.to_thread` overhead. If not available, use
`asyncio.to_thread` as the safe fallback.

Check with: `python -c "import google.genai; c = google.genai.Client(api_key='x'); print(dir(c.aio))"`.

### No Alembic migration in EPIC-001

The `rag.chunks.embedding` column remains `Vector(1536)` after EPIC-001. The new `EmbeddingService`
will produce 768-dimensional vectors, but they cannot be stored in the existing `rag.chunks` table
until EPIC-002 creates the new table structure. This means:

- Search will work against existing 1536d data (old embeddings) with 768d query vectors — the
  cosine similarity results will be meaningless during the transition period.
- This is expected and acceptable for the PoC phase.
- The test `tests/test_models/test_vector_search.py` must be skipped or adapted for EPIC-001.

### asyncio.to_thread vs run_in_executor

`asyncio.to_thread(func, *args)` is equivalent to `loop.run_in_executor(None, func, *args)` but
is the recommended Python 3.9+ API. Both run in the default ThreadPoolExecutor. For production
Cloud Run deployments, the default thread pool size is `min(32, os.cpu_count() + 4)`. This is
sufficient for the expected load at PoC stage.

### EmbedContentConfig task_type

For retrieval, use `task_type="RETRIEVAL_DOCUMENT"` when embedding text chunks that will be stored
and retrieved later, and `task_type="RETRIEVAL_QUERY"` for the query vector at search time.
This distinction improves recall for Gemini embedding models.

Update `generate_single_embedding()` to accept an optional `task_type` parameter:
```python
async def generate_single_embedding(
    self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[float]:
```

And call with `task_type="RETRIEVAL_QUERY"` from `retrieval.py`.

### Import chain verification after deletions

After deleting the 18 files, run:
```bash
python -c "from app.main import app"
```
This will surface any remaining import errors from modules that still reference deleted ones.
Fix these before running the full test suite.

Key import chains to verify manually:
- `app/models/__init__.py` — remove imports of `Document`, `IngestionLog`, `SearchLog`
- `app/core/__init__.py` — remove any star imports or explicit imports of deleted modules
- `app/api/schemas/__init__.py` — remove imports of deleted schema modules

### Test isolation for deleted tables

After deleting `search_log.py` and `ingestion_log.py` models, the `client_with_mock_embeddings`
fixture in `conftest.py` has `DELETE FROM rag.search_logs` and related cleanup SQL. These will
fail if the tables have been dropped. For EPIC-001, the tables still exist in the DB (no Alembic
downgrade), so the DELETE statements won't error — but they should still be cleaned up to avoid
confusion. Remove them in the conftest update.

---

## Environment Variable Summary

| Variable | Action | Default (dev) |
|---|---|---|
| `OPENAI_API_KEY` | Remove | — |
| `GEMINI_API_KEY` | Add | `""` (required) |
| `EMBEDDING_MODEL` | Change value | `text-multilingual-embedding-002` |
| `EMBEDDING_DIMENSIONS` | Change value | `768` |
| `LLM_MODEL` | Change value | `gemini-2.5-flash` |
| `LLM_MAX_OUTPUT_TOKENS` | Change value | `8192` |
| `LLM_TIMEOUT` | Remove | — |

---

## Files Changed Summary

| # | File | Action | Phase |
|---|------|--------|-------|
| 1 | `app/config.py` | Edit | 1 |
| 2 | `.env.example` | Edit | 1 |
| 3 | `pyproject.toml` | Edit | 2 |
| 4 | `app/core/embeddings.py` | Rewrite | 3 |
| 5 | `app/core/generation.py` | Rewrite | 4 |
| 6 | `app/core/retrieval.py` | Edit | 13 |
| 7 | `app/core/ranking.py` | Edit | 14 |
| 8 | `app/api/v1/router.py` | Edit | 11 |
| 9 | `app/dependencies.py` | Edit | 12 |
| 10 | `tests/conftest.py` | Edit | 15 |
| 11 | `tests/test_core/test_embeddings.py` | Rewrite | 16 |
| 12 | `tests/test_core/test_ranking.py` | Edit | 17 |
| 13 | `tests/test_models/test_vector_search.py` | Edit | 18 |
| 14 | `tests/test_api/test_search.py` | Edit | 19 |
| 15–32 | (18 files in deletion list) | Delete | 5–10 |
