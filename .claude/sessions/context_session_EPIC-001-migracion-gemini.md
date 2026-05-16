# Context Session: EPIC-001-migracion-gemini

**Fecha de creación:** 2026-05-16
**Status:** in-progress

## Issue principal

`issues/EPIC-001-migracion-gemini.md`

Sustituir todas las dependencias de OpenAI por el SDK `google-genai`. Adaptar configuración y ajustar la dimensión de los vectores de 1536 → 768. Limpiar el código de estimación legacy.

## Estado del sistema (baseline)

- `app/config.py`: settings OpenAI hardcodeadas (OPENAI_API_KEY, EMBEDDING_MODEL=text-embedding-3-small, EMBEDDING_DIMENSIONS=1536, LLM_MODEL=o4-mini)
- `app/core/embeddings.py`: usa AsyncOpenAI + tiktoken, valida 1536 dims
- `app/core/generation.py`: usa AsyncOpenAI.responses.create(), métodos estimation/validation/fallback legacy
- `app/core/retrieval.py`: SQL con `<=>` coseno 1536d implícita, filtros legacy chunk_type/technologies/costs, usa query_preprocessing
- `app/core/ranking.py`: pesos 0.50/0.25/0.15/0.10 con tech_match y cost_range
- `pyproject.toml`: depende de openai>=1.0 y tiktoken>=0.7

## Planes generados

| Agente | Plan | Fecha |
|---|---|---|
| @vertex-ai-architect | `.claude/doc/EPIC-001-migracion-gemini/vertex-ai-plan.md` | 2026-05-16 |
| @backend-developer | `.claude/doc/EPIC-001-migracion-gemini/backend.md` | 2026-05-16 |
| @qa-criteria-validator | `.claude/doc/EPIC-001-migracion-gemini/qa-report.md` | 2026-05-16 |

## Decisiones clave de AI integration

- SDK: `google-genai>=2.3.0` (NO `google-generativeai`)
- Embeddings: `text-multilingual-embedding-002`, 768 dims
- Generación: `gemini-2.5-flash`
- Async: siempre `client.aio.models.*`
- task_type: `RETRIEVAL_DOCUMENT` al indexar, `RETRIEVAL_QUERY` al buscar
- Retry: ResourceExhausted (4 intentos, 2→4→8→16s), DeadlineExceeded (2, 4→8s), ServiceUnavailable (2, 2→4s)
- Pesos ranking: similarity=0.70, recency=0.30 (eliminar tech_match y cost_range)
- Prompts: todos en `app/core/prompts.py`, nunca inline

## Dependencias de esta epic

- Bloquea: EPIC-002 a EPIC-006
- Depende de: EPIC-000

## Planes generados (continuación)

| Agente | Sección / Archivo | Fecha |
|---|---|---|
| @backend-test-engineer | `issues/EPIC-001-migracion-gemini.md` § Test Strategy | 2026-05-16 |

## Estrategia de tests — resumen ejecutivo (@backend-test-engineer)

### Archivos a modificar
- `tests/conftest.py` — `GEMINI_API_KEY`, mocks 768d, eliminar `live_api`/`--live-api`, simplificar `_make_mock_generation_service`
- `tests/test_core/test_embeddings.py` — REESCRIBIR con mocks de `google-genai` (genai.Client, aio path)
- `tests/test_core/test_ranking.py` — ACTUALIZAR: nueva firma `calculate_final_score(similarity, recency)`, eliminar `technology_match_score`/`cost_range_score` tests
- `tests/test_api/test_search.py` — ADAPTAR: eliminar filtros legacy, helper de ingest, stats; skip tests que dependen de schema 1536d

### Archivos a crear
- `tests/test_core/test_generation.py` — NUEVO: tests de `GenerationService.generate()` con mocks Gemini

### Archivos a ELIMINAR (13 en total)
- `tests/test_core/`: test_chunking.py, test_query_preprocessing.py, test_pipeline.py, test_prompt_builder.py, test_response_parser.py, test_anonymization.py, test_confidence.py
- `tests/test_api/`: test_estimate.py, test_ingest.py, test_stats.py, schemas/test_quote_validation.py
- `tests/test_models/`: test_document.py, test_chunk.py

### Patrón de mock clave
```python
# Mockear client.aio.models (NO client.models — ese bloquea el event loop)
service._client.aio.models.embed_content = AsyncMock(return_value=mock_response)
service._client.aio.models.generate_content = AsyncMock(return_value=mock_response)
```

## Archivos de test actualizados (Wave 3 — RAG-04)

| Archivo | Acción | Fecha |
|---|---|---|
| `tests/test_core/test_ranking.py` | ACTUALIZADO: eliminados `cost_range_score`/`technology_match_score`, nueva firma `calculate_final_score(similarity, recency)`, `ScoredResult` sin campos legacy | 2026-05-16 |
| `tests/test_api/test_search.py` | ACTUALIZADO: eliminados tests con `_ingest_full_quote`, filtros legacy y stats; añadidos tests de endpoints legacy 404 | 2026-05-16 |

## Criterios de Aceptacion (@qa-criteria-validator)

**Seccion escrita en:** `issues/EPIC-001-migracion-gemini.md` § Acceptance Criteria

### TC Classification

| TC   | Descripcion                                             | Tipo       |
|------|---------------------------------------------------------|------------|
| TC-1 | Health check GET /health → 200                         | Paralelo   |
| TC-2 | POST /api/v1/search → 200 sin 500 (embeddings 768d)    | Secuencial |
| TC-3 | Endpoints legacy (estimate/ingest/stats) → 404         | Paralelo   |
| TC-4 | Busqueda semantica con re-ranking 0.70/0.30            | Secuencial |

TC-2 y TC-4 son secuenciales entre si: TC-4 requiere datos creados por TC-2.
TC-1 y TC-3 son paralelos entre si y respecto a los demas.

### Success Criteria — resumen

**Funcionales:** tests unitarios pasan, health=200, endpoints legacy=404, search=200, no ImportError en logs.

**No-funcionales:**
- `grep -r "openai|tiktoken" app/` devuelve 0 resultados
- openai y tiktoken eliminados de pyproject.toml
- google-genai >= 2.3.0 instalado
- EMBEDDING_DIMENSIONS=768 en config.py
- GEMINI_API_KEY (no OPENAI_API_KEY) en config.py
- 17 archivos legacy eliminados (chunk.py diferido a EPIC-002)
- ruff check limpio

### Notas importantes para el implementador

- NO usar Playwright para esta epic — no hay UI. Los TCs son verificaciones via curl/httpx y pytest.
- Los tests de busqueda que insertan en rag.chunks deben llevar @pytest.mark.skip con reason="Pendiente EPIC-002: columna embedding es Vector(1536)" hasta que EPIC-002 migre el schema.
- El endpoint /api/v1/search puede retornar lista vacia si la DB esta vacia — eso es comportamiento correcto, no un fallo.
- Verificar logs en tiempo de arranque (no solo respuestas HTTP) para confirmar ausencia de errores de import.

## Wave 1 TDD — Estado (2026-05-16)

### Archivos creados/modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `.trees/feature-issue-EPIC-001/tests/conftest.py` | Modificado | `GEMINI_API_KEY` en get_test_settings(); mocks 768d; `_make_mock_generation_service` devuelve str; `live_api`/`pytest_addoption` eliminados; cleanup de tablas legacy (`search_logs`, `ingestion_logs`) eliminado; imports de `app.main`/`app.db`/`app.dependencies` diferidos (lazy) para evitar crash en tiktoken |
| `.trees/feature-issue-EPIC-001/tests/test_core/test_config.py` | Creado (nuevo) | 6 tests TDD que verifican el config post-migración a Gemini |

### Resultado de ejecución Wave 1

```
pytest tests/test_core/test_config.py --asyncio-mode=auto
5 FAILED, 1 PASSED
```

Fallos correctos (TDD — esperados):
- `test_gemini_api_key_setting_exists` → `ValidationError: Extra inputs are not permitted` (GEMINI_API_KEY no existe aún)
- `test_embedding_dimensions_is_768` → `AssertionError: assert 1536 == 768`
- `test_embedding_model_is_multilingual` → `AssertionError: assert 'text-embedding-3-small' == 'text-multilingual-embedding-002'`
- `test_llm_model_is_gemini_flash` → `AssertionError: assert 'o4-mini' == 'gemini-2.5-flash'`
- `test_no_openai_api_key` → `AssertionError: assert not True` (OPENAI_API_KEY sigue existiendo)

Pasa correctamente:
- `test_database_schema_is_her` → PASSED (env var DATABASE_SCHEMA=her inyectada al correr pytest)

## RAG-01 — COMPLETADO (2026-05-16)

### Cambios aplicados en `.trees/feature-issue-EPIC-001/app/config.py`

- Eliminado: `OPENAI_API_KEY`, `LLM_TIMEOUT`, `ENABLE_TASK_VALIDATION`, `TASK_VALIDATION_TOP_K`, `TASK_VALIDATION_MIN_SIMILARITY`, `MAX_TASKS_FOR_VALIDATION`
- Modificado: `DATABASE_SCHEMA` default `"rag"` → `"her"`
- Modificado: `EMBEDDING_MODEL` default `"text-embedding-3-small"` → `"text-multilingual-embedding-002"`
- Modificado: `EMBEDDING_DIMENSIONS` default `1536` → `768`
- Modificado: `LLM_MODEL` default `"o4-mini"` → `"gemini-2.5-flash"`
- Modificado: `LLM_MAX_OUTPUT_TOKENS` default `16384` → `8192`
- Añadido: `GEMINI_API_KEY: str = ""`
- Actualizado: validator `embedding_dimensions_must_be_valid` permite `{768, 1536}` durante periodo de transición

### Resultado de tests RAG-01

```
pytest tests/test_core/test_config.py -v
6 passed in 0.73s
```

Nota: `tests/test_api/test_health.py` falla por `ModuleNotFoundError: No module named 'tiktoken'` en `app/core/embeddings.py` — fallo pre-existente, pendiente RAG-02.

## Wave 2 Track A TDD — Estado (2026-05-16)

### Archivos creados/modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `.trees/feature-issue-EPIC-001/tests/test_core/test_embeddings.py` | Reescrito | Tests TDD para EmbeddingService google-genai (768d, aio path, error mapping) |

### Tests escritos (16 en total)

**TestEmbeddingServiceInit** (3 tests):
- `test_client_initialized_with_api_key` — verifica que `genai.Client(api_key=...)` es llamado
- `test_model_stored_on_instance` — `_model` almacenado correctamente
- `test_dimensions_stored_on_instance` — `_dimensions` almacenado correctamente

**TestGenerateSingleEmbedding** (4 tests):
- `test_returns_768_floats` — resultado de 768 floats
- `test_task_type_retrieval_document_by_default` — RETRIEVAL_DOCUMENT por defecto
- `test_task_type_retrieval_query_when_specified` — RETRIEVAL_QUERY se pasa al SDK
- `test_empty_text_raises_embedding_error` — texto vacío → EmbeddingError

**TestGenerateEmbeddings** (4 tests):
- `test_batch_returns_list_of_768_float_lists` — batch devuelve N listas de 768 floats
- `test_batch_preserves_order` — orden de embeddings = orden de textos
- `test_empty_input_returns_empty_without_api_call` — [] → [] sin llamar al SDK
- `test_single_call_to_sdk_for_batch` — exactamente 1 llamada SDK para N textos

**TestErrorHandling** (5 tests):
- `test_resource_exhausted_raises_embedding_error` — quota → EmbeddingError con "Rate limit|quota"
- `test_unauthenticated_raises_embedding_error` — auth error → EmbeddingError con auth msg
- `test_null_vector_raises_embedding_error` — vector de ceros → EmbeddingError
- `test_google_api_call_error_raises_embedding_error` — GoogleAPICallError → EmbeddingError
- `test_empty_embeddings_in_response_raises_embedding_error` — respuesta sin embeddings → EmbeddingError

### Resultado de ejecución Wave 2 Track A (TDD rojo esperado)

```
ERROR tests/test_core/test_embeddings.py
ModuleNotFoundError: No module named 'tiktoken'
```

Fallo correcto — `app/core/embeddings.py` aún usa tiktoken/OpenAI. Los tests pasarán una vez que RAG-02 reescriba embeddings.py con google-genai.

## RAG-02 — COMPLETADO (2026-05-16)

### Cambios aplicados en `.trees/feature-issue-EPIC-001/app/core/embeddings.py`

- Eliminado: `import tiktoken`, `import openai`, `AsyncOpenAI`, `RateLimitError`, `AuthenticationError`, `APIError`
- Eliminado: `_truncate_to_token_limit()`, `MAX_EMBEDDING_TOKENS`, `self._encoder`
- Añadido: `from google import genai`, `from google.genai import types`, `from google.api_core import exceptions as google_exceptions`
- `__init__`: ahora crea `genai.Client(api_key=api_key)`, almacena `_model` y `_dimensions`
- `generate_embeddings`: usa `self._client.aio.models.embed_content(model, contents=texts, config=types.EmbedContentConfig(task_type=..., output_dimensionality=...))`; vector en `response.embeddings[i].values`; null-vector check solo para respuestas de 1 item; mapea `ResourceExhausted` → EmbeddingError("Rate limit / quota..."), `Unauthenticated` → EmbeddingError("Authentication error..."), `GoogleAPICallError` → EmbeddingError("API error...")
- `generate_single_embedding`: valida texto no vacío antes de delegar, acepta `task_type` param

### Resultado de tests RAG-02

```
pytest tests/test_core/test_embeddings.py -v
16 passed in 1.51s
```

## Wave 2 Track B TDD — Estado (2026-05-16)

### Archivos creados/modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `.trees/feature-issue-EPIC-001/tests/test_core/test_generation.py` | Creado (nuevo) | Tests TDD para GenerationService google-genai (gemini-2.5-flash, aio path, retry strategy) |

### Tests escritos (26 en total)

**TestGenerationServiceInit** (4 tests):
- `test_client_initialized_with_api_key` — verifica que `genai.Client(api_key=...)` es llamado
- `test_model_stored` — `_model` almacenado correctamente
- `test_max_output_tokens_stored` — `_max_output_tokens` almacenado correctamente
- `test_default_max_output_tokens_is_8192` — default es 8192

**TestGenerate** (9 tests):
- `test_returns_string` — `generate(prompt)` devuelve el string del modelo
- `test_returns_non_empty_string` — resultado es string no vacío
- `test_with_system_instruction` — system_instruction se pasa en GenerateContentConfig
- `test_none_system_instruction_is_valid` — `None` no lanza error
- `test_empty_response_text_raises_generation_error` — `response.text == None` → GenerationError
- `test_empty_string_response_raises_generation_error` — `response.text == ""` → GenerationError
- `test_uses_gemini_25_flash_model` — model name correcto en la llamada
- `test_prompt_passed_as_contents` — prompt se pasa como contents
- `test_uses_async_path_not_sync` — se usa `client.aio.models` (async path)

**TestRetryStrategy** (11 tests):
- `test_resource_exhausted_retries_and_raises` — 4 reintentos con sleep
- `test_resource_exhausted_uses_exponential_backoff` — delays 2→4→8→16s
- `test_resource_exhausted_total_attempts_is_five` — 5 llamadas totales (1 inicial + 4 reintentos)
- `test_resource_exhausted_succeeds_on_retry` — éxito en reintento retorna texto
- `test_deadline_exceeded_retries_and_raises` — 1 reintento con sleep
- `test_deadline_exceeded_total_attempts_is_two` — 2 llamadas totales
- `test_deadline_exceeded_succeeds_on_retry` — éxito en reintento retorna texto
- `test_unauthenticated_raises_immediately` — sin reintentos (0 sleep calls)
- `test_unauthenticated_single_attempt_only` — exactamente 1 llamada
- `test_other_google_api_error_raises_immediately` — GoogleAPICallError genérico → sin reintentos
- `test_generation_error_wraps_google_exception` — GenerationError tiene mensaje descriptivo

**TestLegacyMethodsAbsent** (4 tests):
- `test_generate_estimation_not_present` — `generate_estimation()` eliminado
- `test_validate_estimation_not_present` — `validate_estimation()` eliminado
- `test_build_fallback_estimation_not_present` — `build_fallback_estimation()` eliminado
- `test_generate_method_is_present` — `generate()` existe y es callable

### Resultado de ejecución Wave 2 Track B (TDD rojo esperado)

```
ERROR tests/test_core/test_generation.py
ModuleNotFoundError: No module named 'openai'
```

Fallo correcto — `app/core/generation.py` aún importa desde `openai`. Los tests pasarán una vez que RAG-03 reescriba generation.py con google-genai (`genai.Client`, `client.aio.models.generate_content`).

## RAG-03 — COMPLETADO (2026-05-16)

### Archivos creados/modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `.trees/feature-issue-EPIC-001/app/core/prompts.py` | Creado | `RAG_SYSTEM_INSTRUCTION` y `RAG_CONTEXT_TEMPLATE` como constantes |
| `.trees/feature-issue-EPIC-001/app/core/generation.py` | Reescrito | `GenerationService` con `genai.Client`, `client.aio.models.generate_content`, retry strategy completa |

### Cambios aplicados en `app/core/generation.py`

- Eliminados: imports de `openai`, `app.core.prompt_builder`, `app.core.response_parser`
- Eliminados métodos legacy: `generate_estimation()`, `validate_estimation()`, `build_fallback_estimation()`, `_call_llm_with_retries()`, `_call_llm()`
- Añadido: `GenerationService.__init__(api_key, model="gemini-2.5-flash", max_output_tokens=8192)` con `genai.Client(api_key=api_key)`
- Añadido: `async generate(prompt, system_instruction=None) -> str` con:
  - `client.aio.models.generate_content(model=..., contents=prompt, config=GenerateContentConfig(...))`
  - Validación de `response.text` (None o string vacío → `GenerationError`)
  - `ResourceExhausted`: 4 reintentos, backoff `[2, 4, 8, 16]s` vía `await asyncio.sleep()`
  - `DeadlineExceeded`: 1 reintento, 4s delay
  - `Unauthenticated`: falla inmediatamente sin reintentos
  - Otros `GoogleAPICallError`: falla inmediatamente sin reintentos

### Resultado de tests RAG-03

```
pytest tests/test_core/test_generation.py -v
28 passed in 3.31s
```

## RAG-05 — COMPLETADO (2026-05-16)

### Archivos eliminados

**app/core/ (10 archivos):** chunking.py, quote_generation_pipeline.py, query_preprocessing.py, reasoning_service.py, prompt_builder.py, quote_prompt_builder.py, pipeline.py, response_parser.py, anonymization.py, confidence.py

**app/api/v1/ (4 archivos):** estimate.py, quote_generator.py, ingest.py, stats.py

**app/models/ (3 archivos, chunk.py NO eliminado):** document.py, ingestion_log.py, search_log.py

**app/services/ (1 archivo):** ingest_service.py

**app/api/schemas/ (7 archivos):** estimate_request.py, estimate_response.py, ingest_response.py, quote_generation.py, quote_input.py, quote_output.py, transcription_analysis.py

**tests/test_core/ (7 archivos):** test_chunking.py, test_query_preprocessing.py, test_pipeline.py, test_prompt_builder.py, test_response_parser.py, test_anonymization.py, test_confidence.py

**tests/test_api/ (4 archivos):** test_estimate.py, test_ingest.py, test_stats.py, schemas/test_quote_validation.py

**tests/test_models/ (2 archivos):** test_document.py, test_chunk.py

### Archivos modificados en RAG-05

| Archivo | Cambios |
|---|---|
| `app/api/v1/router.py` | Solo importa health_router y search_router; eliminados ingest/estimate/stats/quote_generator |
| `app/models/__init__.py` | Solo exporta Base, TimestampMixin, Chunk; eliminados Document, IngestionLog, SearchLog |
| `app/api/schemas/__init__.py` | Solo exporta SearchFilters, SearchRequest, SearchResponse, SearchResultItem |
| `app/dependencies.py` | `get_embedding_service` usa GEMINI_API_KEY; `get_generation_service` sin timeout; eliminados get_ingest_service, get_estimation_pipeline, get_reasoning_service, get_quote_generation_pipeline |
| `app/core/ranking.py` | Eliminados technology_match_score() y cost_range_score(); calculate_final_score(similarity, recency) pesos 0.70/0.30; ScoredResult sin campos technologies/total_cost/currency |
| `app/core/retrieval.py` | Eliminado import query_preprocessing; generate_single_embedding usa task_type="RETRIEVAL_QUERY"; eliminados filtros legacy; eliminado bloque SearchLog; re-ranking solo recency+similarity; detected_technologies=[] y suggested_chunk_types=[] hardcodeados |

### Verificación final

```
grep -r "from app.core.chunking|from app.core.pipeline|from app.core.query_preprocessing|..." app/
# Devuelve vacío — OK
```
