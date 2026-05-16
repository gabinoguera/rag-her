# EPIC-007: Limpieza del Repositorio Legacy — Backend Plan

**Fecha:** 2026-05-16
**Estado:** plan aprobado
**Depende de:** EPIC-001 (completado), EPIC-002 (completado)

---

## Estado del repositorio a la fecha del plan

### Lo que EPIC-001 ya eliminó

EPIC-001 (RAG-05) borró los siguientes módulos y archivos:

- `app/models/document.py`, `ingestion_log.py`, `search_log.py`
- `app/services/ingest_service.py`
- `app/api/schemas/estimate_request.py`, `estimate_response.py`, `ingest_response.py`, `quote_generation.py`, `quote_input.py`, `quote_output.py`, `transcription_analysis.py`
- `app/core/chunking.py`, `query_preprocessing.py`, `quote_generation_pipeline.py`, `prompt_builder.py`, `response_parser.py`, `anonymization.py`, `confidence.py`, `text_processing.py`
- `app/api/v1/ingest.py`, `estimate.py`, `stats.py`
- `tests/test_core/test_chunking.py`, `test_query_preprocessing.py`, `test_pipeline.py`, `test_prompt_builder.py`, `test_response_parser.py`, `test_anonymization.py`, `test_confidence.py`
- `tests/test_api/test_estimate.py`, `test_ingest.py`, `test_stats.py`, `schemas/test_quote_validation.py`
- `tests/test_models/test_document.py`, `test_chunk.py` (parcial)

### Lo que queda por limpiar (estado exacto post-EPIC-001 y post-EPIC-002)

| Artefacto | Tipo | Motivo de permanencia | Acción |
|-----------|------|----------------------|--------|
| `app/models/chunk.py` | Modelo legacy | No eliminado en EPIC-001 (RAG-05 lo dejó como "pendiente") | Eliminar |
| `app/models/__init__.py` | Import | Importa y exporta `Chunk` | Actualizar |
| `app/core/ranking.py` | Módulo legacy | Contiene lógica de re-ranking usada únicamente por `retrieval.py` (rag schema) | Evaluar: mover lógica a `retrieval.py` o mantener separado bajo `her.*` |
| `app/core/retrieval.py` | Servicio legacy | Opera sobre `rag.chunks` — tabla que no existirá en el dominio HER | Eliminar o reescribir para `her.check_in_chunks` en EPIC-004 |
| `app/api/v1/search.py` | Endpoint legacy | Endpoint `/search` opera sobre `rag.chunks` | Eliminar |
| `app/api/v1/router.py` | Router | Solo monta `health` y `search` (legacy) | Actualizar: solo health; checkin/ceo/speech se añaden en sus epics |
| `app/api/schemas/search_request.py` | Schema Pydantic | Específico del endpoint RAG legacy | Eliminar |
| `app/api/schemas/search_response.py` | Schema Pydantic | Específico del endpoint RAG legacy | Eliminar |
| `app/api/schemas/common.py` | Schema Pydantic | Contiene `ErrorResponse` — usado por `search.py` y posiblemente por futuros endpoints | Verificar y mantener si `ErrorResponse` es reutilizable |
| `app/dependencies.py` | Dependencias | `get_retrieval_service()` y `get_generation_service()` sin consumidores activos tras eliminar search | Limpiar dependencias huérfanas |
| `app/main.py` | Entrypoint | Título "RAG Estimation Service", logs mencionan "RAG Estimation Service" | Actualizar título, descripción y mensajes de log |
| `README.md` | Documentación | Describe el servicio de estimación de presupuestos con OpenAI | Reescribir para HER |
| `alembic/versions/001-005` | Migraciones | Crean schema `rag`, extensiones, `rag.documents`, `rag.chunks`, `rag.ingestion_logs`, `rag.search_logs` | Archivar o documentar como legacy |
| `estimation_samples/` | Datos de ejemplo | JSON con presupuestos de proyectos ficticios | Eliminar directorio |
| `transcriptions/` | Datos de ejemplo | TXT con transcripciones de ejemplo | Eliminar directorio |
| `tests/test_core/test_ranking.py` | Tests | Testea `app/core/ranking.py` — si se elimina o refactoriza, los tests cambian | Mover lógica de ranking a retrieval HER o reubicar tests |
| `tests/test_api/test_search.py` | Tests | 3 tests activos (validación HTTP 400/422), 3 tests con `@skip` por rag schema | Eliminar junto con endpoint |
| `tests/test_models/test_vector_search.py` | Tests | Marcado con `pytestmark = pytest.mark.skip` — pendiente EPIC-002 | Reescribir en EPIC-002 (ya en scope de EPIC-002) |
| `app/config.py` | Configuración | `HNSW_EF_SEARCH`, `EMBEDDING_DIMENSIONS` con validación `{768, 1536}` — 1536 es legacy OpenAI | Actualizar validación a solo 768 |
| `estrategia-chunking-vectorizacion.md` | Documentación | Documento de estrategia del RAG de estimaciones | Eliminar o archivar |

### Dependencias entre módulos (grafo de eliminación)

```
app/api/v1/search.py
  └─ app/core/retrieval.py
       ├─ app/core/ranking.py          <- puede mantenerse con refactor para HER
       ├─ app/api/schemas/search_request.py
       └─ app/api/schemas/search_response.py

app/models/chunk.py
  └─ app/models/__init__.py (Chunk export)

tests/test_api/test_search.py
  └─ (eliminar junto con search.py)

tests/test_core/test_ranking.py
  └─ (mover o adaptar si ranking.py se refactoriza para HER)
```

---

## Decisión arquitectónica: ¿qué hacer con `ranking.py` y `retrieval.py`?

`app/core/ranking.py` contiene lógica genérica (recency score, weighted composite score, deduplication) que **es reutilizable** para el dominio HER (`her.check_in_chunks`). EPIC-004 necesitará exactamente este tipo de re-ranking para el CEO query service.

**Recomendación:**
- Mantener `app/core/ranking.py` tal cual — la lógica de `recency_score` y `calculate_final_score` es domain-agnostic.
- Eliminar `app/core/retrieval.py` en esta epic (opera sobre `rag.chunks`).
- EPIC-004 creará `app/core/retrieval.py` de nuevo, apuntando a `her.check_in_chunks`.
- Los tests de `test_ranking.py` **se mantienen** — cubren lógica que sobrevive la limpieza.

**Implicación:** `app/api/v1/search.py` y sus dependencias directas (`retrieval.py`, `search_request.py`, `search_response.py`) se eliminan. `ranking.py` se conserva.

---

## Archivos a crear

Ninguno. Esta epic es exclusivamente de eliminación y actualización.

---

## Archivos a eliminar

```
app/models/chunk.py
app/core/retrieval.py
app/api/v1/search.py
app/api/schemas/search_request.py
app/api/schemas/search_response.py
estimation_samples/                    (directorio completo)
transcriptions/                        (directorio completo)
estrategia-chunking-vectorizacion.md
tests/test_api/test_search.py
tests/test_models/test_vector_search.py  (marcado skip, pendiente EPIC-002 — eliminar aquí)
```

**Nota:** `tests/test_models/test_vector_search.py` se elimina porque la nota en el archivo indica que será reescrito cuando EPIC-002 cree los nuevos modelos. Si EPIC-002 ya está completado (merge del PR #2), este archivo ya debería haber sido reemplazado. Verificar antes de eliminar.

---

## Archivos a modificar

### 1. `app/models/__init__.py`

**Estado actual:**
```python
from app.models.base import Base, TimestampMixin
from app.models.chunk import Chunk

__all__ = ["Base", "TimestampMixin", "Chunk"]
```

**Estado objetivo:**
```python
from app.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

**Nota:** Si EPIC-002 ya creó `HerBase` y los modelos `Employee`, `CheckIn`, `CheckInChunk`, estos deben exportarse también aquí. Verificar `app/models/` antes de modificar — puede que ya existan `employee.py`, `checkin.py`, `checkin_chunk.py` en el worktree de EPIC-002.

### 2. `app/api/v1/router.py`

**Estado actual:**
```python
from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.search import router as search_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(search_router, tags=["search"])
```

**Estado objetivo:**
```python
from fastapi import APIRouter
from app.api.v1.health import router as health_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
```

**Nota:** `checkin_router`, `ceo_router`, y `speech_router` se añadirán en EPIC-003/004/005 respectivamente. No adelantar imports que aún no existen.

### 3. `app/main.py`

**Cambios requeridos:**

a. Título y descripción de la aplicación FastAPI:
```python
# Antes
application = FastAPI(
    title="RAG Estimation Service",
    description="AI-powered software estimation service using RAG",
    version="0.1.0",
    ...
)

# Después
application = FastAPI(
    title="HER — Conversational Intelligence API",
    description="Backend conversacional para check-ins de empleados con análisis semántico vía Gemini.",
    version="0.2.0",
    ...
)
```

b. Mensajes de log en `lifespan`:
```python
# Antes
await logger.ainfo(
    "Starting RAG Estimation Service",
    ...
)
# ...
await logger.ainfo("Shutting down RAG Estimation Service")

# Después
await logger.ainfo(
    "Starting HER Conversational Intelligence API",
    ...
)
# ...
await logger.ainfo("Shutting down HER Conversational Intelligence API")
```

c. Mount StaticFiles para `adapters/primary/web/` (si el directorio existe en el momento de implementar):
```python
import os
from fastapi.staticfiles import StaticFiles

# En create_app(), tras include_router:
web_dir = os.path.join(os.path.dirname(__file__), "..", "adapters", "primary", "web")
if os.path.isdir(web_dir):
    application.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
```

**Nota importante:** El mount de StaticFiles debe ser el ÚLTIMO mount registrado, después de todos los routers de API. Un `StaticFiles` montado en `/` captura todas las rutas no resueltas. Si el directorio `adapters/primary/web/` no existe aún, el mount debe ser condicional (como se muestra arriba con `os.path.isdir`).

### 4. `app/dependencies.py`

**Estado actual:** Contiene `get_retrieval_service()` y `get_generation_service()` sin consumidores tras eliminar `search.py`.

**Cambios:**
- Eliminar la función `get_retrieval_service()` y su import lazy de `RetrievalService`.
- Mantener `get_generation_service()` — será consumido por EPIC-004 (`ceo_service.py`).
- Mantener `get_embedding_service()` — será consumido por EPIC-003 (`checkin_service.py`).
- Mantener `get_db_session()` — consumido por todos los servicios futuros.

```python
# Eliminar este bloque:
async def get_retrieval_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    settings: Settings = Depends(get_settings),
) -> "RetrievalService":
    from app.core.retrieval import RetrievalService
    return RetrievalService(db=db, embedding_service=embedding_service, settings=settings)
```

### 5. `app/config.py`

**Cambio específico:** El validador `embedding_dimensions_must_be_valid` actualmente permite `{768, 1536}`. El valor 1536 corresponde a `text-embedding-ada-002` de OpenAI (legacy). El modelo Gemini `text-multilingual-embedding-002` usa 768 dimensiones exclusivamente.

```python
# Antes
allowed = {768, 1536}

# Después
allowed = {768}
```

**Nota:** Verificar si hay tests que pasen `EMBEDDING_DIMENSIONS=1536` en fixtures. `tests/test_core/test_config.py` puede contener casos que testean este valor — actualizar en consecuencia.

### 6. `README.md`

**Reescritura completa.** El README actual describe:
- Servicio de estimación de presupuestos con RAG
- Referencia a OpenAI API key
- Endpoints legacy (`/ingest`, `/search`, `/estimate`)

**Contenido objetivo:**
- Descripción de HER: plataforma de inteligencia conversacional para check-ins de empleados
- Prerequisitos: Python 3.11+, Docker, Google Cloud credentials (Gemini API key + service account)
- Variables de entorno relevantes: `GEMINI_API_KEY`, `DATABASE_URL`, `GOOGLE_APPLICATION_CREDENTIALS`
- Endpoints disponibles tras EPIC-001..007: `GET /api/v1/health`
- Arquitectura: `app/core/` (embeddings, generation, speech, tts), `app/models/` (Employee, CheckIn, CheckInChunk), `app/api/v1/` (health, checkin, ceo, speech — últimos 3 pendientes de epics posteriores)

### 7. Alembic — migraciones 001-005

**Decisión:** NO eliminar las migraciones existentes. Son parte del historial de Alembic y eliminadas romperían la cadena `down_revision`.

**Acción:** Añadir un comentario de archivo en la cabecera de cada migración 001-005:

```python
"""Create extensions and schema.

LEGACY: Esta migración pertenece al dominio RAG de estimaciones (pre-HER).
El schema 'rag' y sus tablas ya no se usan. Se conserva para mantener
la cadena de revisiones Alembic. Ver EPIC-007 para contexto.

Revision ID: 001
...
"""
```

**Nota:** Las migraciones 006-009 (schema `her`) están en el worktree de EPIC-002. Una vez mergeado el PR #2, serán parte del historial principal y son las migraciones activas del dominio HER.

---

## Fases de implementación

### Fase 1 — Eliminar modelos y datos de ejemplo (paralelo)

**Tarea CLEAN-02 parcial + CLEAN-03**

Archivos a eliminar:
- `app/models/chunk.py`
- `estimation_samples/` (directorio)
- `transcriptions/` (directorio)
- `estrategia-chunking-vectorizacion.md`

Archivos a modificar:
- `app/models/__init__.py` — quitar import/export de `Chunk`

**Verificación:** `python -c "from app.models import Base, TimestampMixin; print('OK')"` sin errores.

### Fase 2 — Eliminar endpoint de búsqueda legacy (depende de Fase 1)

**Tarea CLEAN-01 + CLEAN-04**

Archivos a eliminar:
- `app/core/retrieval.py`
- `app/api/v1/search.py`
- `app/api/schemas/search_request.py`
- `app/api/schemas/search_response.py`
- `tests/test_api/test_search.py`

Archivos a modificar:
- `app/api/v1/router.py` — quitar `search_router`
- `app/dependencies.py` — quitar `get_retrieval_service()`
- `app/config.py` — actualizar validador `EMBEDDING_DIMENSIONS` a `{768}`

**Verificación:** `python -m pytest tests/ --asyncio-mode=auto -x` — todos los tests pasan excepto los marcados con skip explícito.

### Fase 3 — Actualizar entrypoint y documentación (depende de Fase 2)

**Tarea CLEAN-05 + CLEAN-06**

Archivos a modificar:
- `app/main.py` — título HER, mensajes de log, StaticFiles condicional
- `README.md` — reescritura completa

Archivos a anotar (no eliminar):
- `alembic/versions/001_create_extensions_and_schema.py` — añadir comentario LEGACY
- `alembic/versions/002_create_documents_table.py` — añadir comentario LEGACY
- `alembic/versions/003_create_chunks_table.py` — añadir comentario LEGACY
- `alembic/versions/004_create_ingestion_logs_table.py` — añadir comentario LEGACY
- `alembic/versions/005_create_search_logs_table.py` — añadir comentario LEGACY

**Verificación final:**
```bash
grep -r "RAG Estimation" app/         # debe devolver vacío
grep -r "rag\." app/ --include="*.py" # debe devolver vacío
python -m pytest tests/ --asyncio-mode=auto   # todos los tests pasan
```

---

## Test Strategy

### Tests que se eliminan

| Archivo | Motivo |
|---------|--------|
| `tests/test_api/test_search.py` | El endpoint `/search` se elimina; los 3 tests activos (400/422) son redundantes una vez que el endpoint no existe |
| `tests/test_models/test_vector_search.py` | Marcado con skip global, pendiente EPIC-002; si EPIC-002 ya mergeó con su reescritura, verificar si existe reemplazo |

### Tests que se mantienen

| Archivo | Estado post-limpieza |
|---------|---------------------|
| `tests/test_core/test_ranking.py` | Se mantiene — `app/core/ranking.py` se conserva |
| `tests/test_core/test_embeddings.py` | Se mantiene — `app/core/embeddings.py` no cambia |
| `tests/test_core/test_generation.py` | Se mantiene — `app/core/generation.py` no cambia |
| `tests/test_core/test_config.py` | Actualizar el test que verifica `EMBEDDING_DIMENSIONS=1536` como válido |
| `tests/test_api/test_health.py` | Se mantiene — no depende de search |

### Test de regresión post-limpieza

```bash
# Verificar que no quedan imports rotos
python -c "import app.main; print('main OK')"
python -c "from app.api.v1.router import router; print('router OK')"
python -c "from app.models import Base, TimestampMixin; print('models OK')"

# Suite completa
python -m pytest tests/ --asyncio-mode=auto -v

# Resultado esperado:
# - test_ranking.py: 11 passed
# - test_embeddings.py: passed
# - test_generation.py: passed
# - test_health.py: passed
# - test_config.py: passed (con ajuste del test de 1536)
# - 0 errores de import
```

### Caso especial: `tests/test_core/test_config.py`

El validador `embedding_dimensions_must_be_valid` actualmente acepta 1536. Si el test contiene:
```python
def test_embedding_dimensions_1536_valid():
    settings = Settings(EMBEDDING_DIMENSIONS=1536, ...)
    assert settings.EMBEDDING_DIMENSIONS == 1536
```
Este test fallará tras cambiar `allowed = {768}`. Cambiar el test para verificar que 1536 lanza `ValueError`.

---

## Acceptance Criteria

| AC | Criterio | Verificación |
|----|----------|--------------|
| AC-1 | `app/models/chunk.py` no existe | `ls app/models/` no muestra `chunk.py` |
| AC-2 | No hay referencias a `rag.` en código Python | `grep -r "rag\." app/ --include="*.py"` devuelve vacío |
| AC-3 | No hay referencias a `RAG Estimation` | `grep -r "RAG Estimation" app/` devuelve vacío |
| AC-4 | `app/api/v1/router.py` solo monta `health_router` | `cat app/api/v1/router.py` no menciona `search` |
| AC-5 | `/api/v1/search` devuelve 404 | `curl -X POST http://localhost:8000/api/v1/search` → 404 |
| AC-6 | `estimation_samples/` no existe | `ls estimation_samples/` → error |
| AC-7 | `transcriptions/` no existe | `ls transcriptions/` → error |
| AC-8 | `FastAPI(title=...)` contiene "HER" | `grep "title" app/main.py` → "HER — Conversational Intelligence API" |
| AC-9 | `app/core/ranking.py` existe y sus tests pasan | `pytest tests/test_core/test_ranking.py` → 11 passed |
| AC-10 | Suite completa pasa sin errores de import | `pytest tests/ --asyncio-mode=auto` → 0 errors, 0 unexpected failures |
| AC-11 | `EMBEDDING_DIMENSIONS=1536` lanza `ValueError` en config | test unitario en `test_config.py` verifica el ValueError |

---

## Variables de entorno

No se añaden nuevas variables de entorno en esta epic.

**Cambio en validación existente:**
- `EMBEDDING_DIMENSIONS`: valor permitido pasa de `{768, 1536}` a `{768}`. Actualizar `.env.example` eliminando cualquier mención a 1536.

---

## Riesgos y notas importantes

### Riesgo 1: EPIC-002 no mergeado a `main`

Las migraciones 006-009 y los modelos `Employee`, `CheckIn`, `CheckInChunk` están en el worktree `.trees/feature-issue-EPIC-002`. Si EPIC-007 se ejecuta antes de que ese PR mergee, `app/models/__init__.py` debe exportar solo `Base, TimestampMixin`. Si ya mergeó, exportar también los tres modelos HER.

**Verificación previa:**
```bash
ls app/models/  # si aparecen employee.py, checkin.py, checkin_chunk.py → EPIC-002 mergeado
```

### Riesgo 2: StaticFiles y rutas API

El mount `StaticFiles(directory=web_dir, html=True)` en `/` debe registrarse **después** de todos los routers. Si se registra antes, capturará las rutas `/api/v1/*` antes de que el router las resuelva. La implementación condicional con `os.path.isdir` mitiga el riesgo cuando el directorio no existe.

### Riesgo 3: `app/api/schemas/common.py`

`common.py` contiene `ErrorResponse`. Verificar si otros módulos futuros (EPIC-003, EPIC-004) lo importarán. Si es así, mantenerlo. Si no hay ningún consumidor activo, puede eliminarse junto con `search_request.py` y `search_response.py`. Decisión conservadora: mantener `common.py`.

### Riesgo 4: Alembic head tras EPIC-002

Con EPIC-002 mergeado, el head de Alembic es `009`. Las migraciones 001-005 se anotan como legacy pero no se tocan funcionalmente. El `down_revision` de la migración 006 apunta a `005` — esta cadena debe preservarse.

### Nota sobre `almawolf-7bbb108314b5.json`

En la raíz del repositorio hay un archivo `almawolf-7bbb108314b5.json` que parece ser un service account de Google Cloud. Este archivo no pertenece al scope de EPIC-007 pero **nunca debe commitearse**. Verificar que está en `.gitignore`.

---

## Appendix

### Inventario completo post-limpieza (estado objetivo)

```
app/
  api/
    schemas/
      __init__.py
      common.py           # ErrorResponse — mantener
    v1/
      __init__.py
      health.py
      router.py           # solo health_router
  core/
    __init__.py
    embeddings.py
    generation.py
    prompts.py
    ranking.py            # mantener — reutilizable en HER
  models/
    __init__.py           # Base, TimestampMixin (+ HER models si EPIC-002 mergeado)
    base.py
    # employee.py, checkin.py, checkin_chunk.py si EPIC-002 mergeado
  services/
    __init__.py
  config.py               # EMBEDDING_DIMENSIONS solo {768}
  db.py
  dependencies.py         # sin get_retrieval_service
  main.py                 # título HER
  utils/

alembic/
  versions/
    001_*.py              # anotado LEGACY
    002_*.py              # anotado LEGACY
    003_*.py              # anotado LEGACY
    004_*.py              # anotado LEGACY
    005_*.py              # anotado LEGACY
    # 006-009 de EPIC-002 tras merge

tests/
  test_core/
    test_config.py        # actualizar test de 1536
    test_embeddings.py
    test_generation.py
    test_ranking.py       # mantener
    test_text_processing.py
  test_api/
    test_health.py
    schemas/              # si tiene contenido, verificar
  test_models/
    test_vector_search.py # eliminar (skip global, pendiente EPIC-002)
    # test_her_models.py de EPIC-002 tras merge
```

### Referencia de comandos de verificación

```bash
# Ninguna referencia al schema rag en Python
grep -r "rag\." app/ --include="*.py"

# Ninguna referencia al título legacy
grep -r "RAG Estimation" app/

# Ningún import de chunk legacy
grep -r "from app.models.chunk" app/

# Ningún import de retrieval legacy
grep -r "from app.core.retrieval" app/

# Ningún import de search legacy
grep -r "from app.api.v1.search" app/

# Tests pasan
python -m pytest tests/ --asyncio-mode=auto -v
```
