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
