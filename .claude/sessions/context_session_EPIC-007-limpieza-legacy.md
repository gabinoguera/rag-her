# Context Session: EPIC-007-limpieza-legacy

**Fecha de creación:** 2026-05-16
**Status:** QA PASSED — ready to merge

## Issue principal

`issues/EPIC-007-limpieza-legacy.md`

Eliminar todo el código residual del dominio RAG de estimaciones. Dejar el repositorio limpio y coherente con el dominio HER.

## Estado del sistema al generar el plan (baseline)

### Directorio app/models/
- `base.py` — `Base` con `MetaData(schema="rag")` y `TimestampMixin` con UUID + created_at
- `chunk.py` — modelo legacy `Vector(1536)`, FK a `rag.documents` — PENDIENTE ELIMINAR
- `__init__.py` — exporta `Base`, `TimestampMixin`, `Chunk` — PENDIENTE ACTUALIZAR

### Directorio app/core/
- `embeddings.py` — EmbeddingService, Gemini, 768 dims — CONSERVAR
- `generation.py` — GenerationService, gemini-2.5-flash — CONSERVAR
- `prompts.py` — constantes de prompts — CONSERVAR
- `ranking.py` — recency_score, calculate_final_score, deduplicate_results — CONSERVAR (reutilizable EPIC-004)
- `retrieval.py` — RetrievalService, SQL sobre `rag.chunks` — PENDIENTE ELIMINAR

### Directorio app/api/v1/
- `health.py` — CONSERVAR
- `router.py` — monta health_router + search_router — PENDIENTE ACTUALIZAR (solo health)
- `search.py` — endpoint `/search` sobre `rag.chunks` — PENDIENTE ELIMINAR

### Directorio app/api/schemas/
- `common.py` — ErrorResponse — CONSERVAR
- `search_request.py` — solo usado por search.py — PENDIENTE ELIMINAR
- `search_response.py` — solo usado por search.py — PENDIENTE ELIMINAR

### app/main.py
- Título: "RAG Estimation Service" — PENDIENTE ACTUALIZAR a "HER — Conversational Intelligence API"
- Logs: "Starting RAG Estimation Service" — PENDIENTE ACTUALIZAR

### app/config.py
- `EMBEDDING_DIMENSIONS` validador: `allowed = {768, 1536}` — PENDIENTE ACTUALIZAR a `{768}`
- `DATABASE_SCHEMA = "her"` — ya correcto

### app/dependencies.py
- `get_retrieval_service()` — huérfana tras eliminar search.py — PENDIENTE ELIMINAR
- `get_embedding_service()`, `get_generation_service()`, `get_db_session()` — CONSERVAR

### Alembic
- Migraciones 001-005: schema `rag`, tablas legacy — ANOTAR COMO LEGACY (no eliminar)
- Migraciones 006-009: schema `her` — en worktree EPIC-002, pendiente merge

### Tests
- `tests/test_core/test_ranking.py` — 11 tests activos — CONSERVAR
- `tests/test_api/test_search.py` — 3 activos + 3 skipped por rag schema — PENDIENTE ELIMINAR
- `tests/test_models/test_vector_search.py` — skip global — PENDIENTE ELIMINAR
- `tests/test_core/test_config.py` — contiene test que valida 1536 como válido — PENDIENTE ACTUALIZAR

### Datos legacy
- `estimation_samples/` — 10+ JSON de proyectos ficticios — PENDIENTE ELIMINAR
- `transcriptions/` — 6 TXT — PENDIENTE ELIMINAR
- `estrategia-chunking-vectorizacion.md` — PENDIENTE ELIMINAR

## Planes generados

| Agente | Sección / Archivo | Fecha |
|--------|-------------------|-------|
| @backend-developer | `.claude/doc/EPIC-007-limpieza-legacy/backend.md` + `issues/EPIC-007-limpieza-legacy.md` § Technical Spec | 2026-05-16 |

## Decisiones clave de arquitectura

- `app/core/ranking.py` se **conserva** — lógica domain-agnostic reutilizable en EPIC-004 (CEO query service sobre `her.check_in_chunks`)
- `app/core/retrieval.py` se **elimina** — apunta a `rag.chunks`; EPIC-004 creará uno nuevo para `her.check_in_chunks`
- Migraciones 001-005 se **anotan como LEGACY** pero no se eliminan (preservar cadena `down_revision`)
- StaticFiles mount en `main.py` es **condicional** — solo si `adapters/primary/web/` existe en disco
- `app/api/schemas/common.py` (ErrorResponse) se **conserva** — reutilizable por endpoints futuros

## Precondición crítica antes de implementar

Verificar si EPIC-002 mergeó a `main`:
```bash
ls app/models/  # si aparecen employee.py, checkin.py, checkin_chunk.py → EPIC-002 mergeado
```
Si EPIC-002 ya mergeó: `app/models/__init__.py` debe exportar también los modelos HER.
Si no mergeó: exportar solo `Base, TimestampMixin`.

## Notas de Progreso

### 2026-05-16 — Implementación completada

**Estado:** implementado en worktree `.trees/feature-issue-EPIC-007/`

**Plan utilizado:** `.claude/doc/EPIC-007-limpieza-legacy/backend.md`

**Archivos eliminados (git rm):**
- `app/models/chunk.py`
- `app/core/retrieval.py`
- `app/api/v1/search.py`
- `app/api/schemas/search_request.py`
- `app/api/schemas/search_response.py`
- `tests/test_api/test_search.py`
- `tests/test_models/test_vector_search.py`
- `estrategia-chunking-vectorizacion.md`
- `estimation_samples/` (15 JSON files)
- `transcriptions/` (6 TXT files)

**Archivos modificados:**
- `app/models/__init__.py` — quitado import/export de `Chunk`
- `app/api/v1/router.py` — eliminado `search_router`
- `app/dependencies.py` — eliminado `get_retrieval_service()`
- `app/config.py` — `EMBEDDING_DIMENSIONS` allowed = `{768}` (era `{768, 1536}`)
- `app/main.py` — título HER, logs HER, StaticFiles condicional, versión 0.2.0
- `README.md` — reescrito para dominio HER
- `alembic/versions/001-005` — anotados como `[LEGACY]` en docstring
- `tests/test_core/test_config.py` — añadido `test_embedding_dimensions_1536_raises_error`

**Resultado de tests:** 106 passed, 0 failed, 2 warnings (SAWarning innocuo de SQLAlchemy)

**Verificaciones de AC:**
- AC-1: chunk.py eliminado
- AC-2: `grep -r "rag\." app/ --include="*.py"` → vacío
- AC-3: `grep -r "RAG Estimation" app/` → vacío
- AC-4: router.py sin mención a "search"
- AC-6: `estimation_samples/` → No such file or directory
- AC-7: `transcriptions/` → No such file or directory
- AC-8: `grep "title" app/main.py` → "HER — Conversational Intelligence API"
- AC-9: `app/core/ranking.py` conservado, 11 tests pasan
- AC-10: 106 passed, 0 errors
- AC-11: test `test_embedding_dimensions_1536_raises_error` añadido y pasa

## QA

**Fecha:** 2026-05-16
**Agente:** qa-acceptance-testing
**Veredicto:** PASSED — Ready to merge
**Reporte:** `.claude/doc/EPIC-007-limpieza-legacy/qa-report.md`

### Resumen de TCs ejecutados

| TC   | Resultado | Evidencia                              |
|------|-----------|----------------------------------------|
| TC-1 | PASSED    | 106 passed, 0 failed                   |
| TC-2 | PASSED    | grep rag.* → vacío                     |
| TC-3 | PASSED    | ValidationError lanzado para 1536      |
| TC-4 | PASSED    | titulo "HER — Conversational..."       |
| TC-5 | PASSED    | test_ranking.py 11/11                  |
