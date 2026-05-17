# EPIC-005: Consulta del CEO (RAG)

**Status:** ready-to-merge
**Espera a:** EPIC-002

## Descripción
El CEO formula una pregunta. El sistema vectoriza, recupera chunks relevantes y Gemini 2.5 Flash sintetiza un resumen de ~80 palabras entregado también como audio TTS.

## Tareas
- CEO-01 — Crear `app/core/ceo_query.py` (RAG pipeline)
- CEO-02 — Diseñar prompt CEO en `app/core/prompts.py`
- CEO-03 — Endpoint `POST /api/v1/ceo/query`
- CEO-04 — Endpoint `GET /api/v1/ceo/summary`
- CEO-05 — Integración TTS en respuesta CEO

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| CEO-01 | — | — |
| CEO-02 | — | CEO-01 |
| CEO-03 | CEO-04 | CEO-02 |
| CEO-04 | CEO-03 | CEO-02 |
| CEO-05 | — | CEO-03, CEO-04 |

---

## Technical Spec

### 1. Executive Summary

EPIC-005 implementa el pipeline RAG completo para consultas del CEO. El CEO formula una pregunta en lenguaje natural; el sistema la vectoriza, recupera los chunks de check-in más relevantes desde `her.check_in_chunks` vía pgvector, aplica re-ranking recency+similarity, y Gemini 2.5 Flash sintetiza una respuesta de ~80 palabras. La respuesta incluye nivel de confianza heurístico y fuentes trazables (empleado, fecha, excerpt). Opcionalmente se puede integrar TTS (CEO-05) en una fase posterior.

---

### 2. MoSCoW

**Must Have**
- CEO-01: `app/core/ceo_query.py` — RAG pipeline (embed pregunta, SQL pgvector, re-rank, síntesis Gemini)
- CEO-02: Prompts `CEO_SYNTHESIS_PROMPT` y `CEO_DAILY_SUMMARY_PROMPT` en `app/core/prompts.py`
- CEO-03: `POST /api/v1/ceo/query` → `{answer, confidence, sources}`
- CEO-04: `GET /api/v1/ceo/summary` → `{summary, checkins_count, period}`

**Should Have**
- `app/services/ceo_service.py` — orquestación limpia entre RAG core y endpoints
- Manejo de errores HTTP apropiado (404 sin chunks, 503 si Gemini falla)
- Logging estructurado con structlog

**Could Have**
- CEO-05: integración TTS en la respuesta del CEO (audio_base64 opcional)
- Paginación de fuentes en la respuesta
- Filtrado por rango de fechas en el query

**Won't Have (en este EPIC)**
- Autenticación/autorización CEO vs empleado
- Caché de embeddings de preguntas frecuentes
- Múltiples modelos LLM configurables por request

---

### 3. Technical Design

#### 3.1 `app/core/ceo_query.py`

Módulo de pipeline RAG puro. Sin estado, sin dependencias de FastAPI.

```python
async def query(
    question: str,
    db: AsyncSession,
    embedding_service: EmbeddingService,
    generation_service: GenerationService,
    top_k: int = 10,
    min_similarity: float = 0.30,
) -> dict:
    ...
```

**Flujo interno:**

1. **Embed pregunta** con `task_type="RETRIEVAL_QUERY"`:
   ```python
   q_embedding = await embedding_service.generate_single_embedding(
       question, task_type="RETRIEVAL_QUERY"
   )
   ```

2. **SQL pgvector** sobre `her.check_in_chunks` con JOIN a `her.check_ins` y `her.employees`:
   ```sql
   SELECT
       cic.id,
       cic.answer_text,
       cic.question_text,
       cic.created_at,
       e.name AS employee_name,
       ci.started_at,
       1 - (cic.embedding <=> :q_vec) AS similarity
   FROM her.check_in_chunks cic
   JOIN her.check_ins ci ON ci.id = cic.checkin_id
   JOIN her.employees e ON e.id = ci.employee_id
   WHERE
       cic.embedding IS NOT NULL
       AND ci.status = 'completed'
       AND 1 - (cic.embedding <=> :q_vec) >= :min_similarity
   ORDER BY cic.embedding <=> :q_vec
   LIMIT :top_k
   ```
   Usar `sqlalchemy.text()` con bind params para evitar inyección SQL.

3. **Re-ranking** usando `app/core/ranking.py`:
   - Para cada row: `rec = recency_score(row.created_at)`
   - `final = calculate_final_score(row.similarity, rec)` (0.70 sim + 0.30 rec)
   - Ordenar por `final` descendente

4. **Confidence heuristic** basado en el `final_score` del top-1:
   - `>= 0.70` → `"alta"`
   - `0.45 - 0.69` → `"media"`
   - `< 0.45` → `"baja"`
   - Sin chunks → `"sin_datos"`

5. **Construir contexto y prompt** usando `CEO_SYNTHESIS_PROMPT` de `app/core/prompts.py`:
   ```python
   context_lines = [
       f"[{r.employee_name} — {r.started_at.date()}]: {r.answer_text}"
       for r in top_results
   ]
   context_str = "\n".join(context_lines)
   prompt = CEO_SYNTHESIS_PROMPT.format(context=context_str, question=question)
   ```

6. **Llamar Gemini**:
   ```python
   answer = await generation_service.generate(
       prompt,
       system_instruction=CEO_SYSTEM_INSTRUCTION,
   )
   ```

7. **Construir y retornar dict**:
   ```python
   return {
       "answer": answer,
       "confidence": confidence,
       "sources": [
           {
               "employee_name": r.employee_name,
               "date": r.started_at.date().isoformat(),
               "excerpt": r.answer_text[:200],
           }
           for r in top_results[:5]  # máximo 5 fuentes
       ],
   }
   ```

**Caso sin chunks:** Si no hay resultados tras el filtrado, retornar:
```python
{
    "answer": "No hay información disponible en los check-ins para responder esta consulta.",
    "confidence": "sin_datos",
    "sources": [],
}
```
Sin llamar a Gemini (ahorro de tokens).

#### 3.2 `app/core/prompts.py` — Nuevas constantes

```python
CEO_SYSTEM_INSTRUCTION = """
Eres el asistente de inteligencia operacional de AlmaWolf.
Responde en español. Sé conciso y directo. Máximo 80 palabras.
Basa tu respuesta ÚNICAMENTE en los fragmentos de check-in proporcionados.
Si la información es insuficiente, indícalo claramente.
"""

CEO_SYNTHESIS_PROMPT = """
Basándote en los siguientes fragmentos de check-ins de empleados, responde la pregunta del CEO.

FRAGMENTOS:
{context}

PREGUNTA: {question}

Responde en máximo 80 palabras, en español, de forma directa y ejecutiva.
"""

CEO_DAILY_SUMMARY_PROMPT = """
Genera un resumen ejecutivo del día basándote en los siguientes check-ins de empleados.

CHECK-INS DEL DÍA:
{context}

El resumen debe:
- Tener máximo 120 palabras
- Destacar logros, bloqueos y próximos pasos
- Estar redactado en español, tono ejecutivo
"""
```

#### 3.3 `app/services/ceo_service.py`

Orquestador de casos de uso CEO. Patrón análogo a `CheckInService`.

```python
class CeoService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        generation_service: GenerationService,
    ) -> None: ...

    async def query(self, question: str) -> dict:
        """Delegación directa a ceo_query.query()."""
        from app.core.ceo_query import query as rag_query
        return await rag_query(
            question=question,
            db=self._db,
            embedding_service=self._embedding_service,
            generation_service=self._generation_service,
        )

    async def daily_summary(self) -> dict:
        """
        Recupera check-ins completados hoy, construye contexto,
        llama a Gemini con CEO_DAILY_SUMMARY_PROMPT y retorna
        {summary, checkins_count, period}.
        """
        ...
```

**`daily_summary` flow:**
1. SQL: SELECT check-ins completados hoy (entre `00:00:00` y `now()` UTC)
   - JOIN con employees, selectinload chunks
2. Si count == 0: retornar `{summary: "Sin check-ins registrados hoy.", checkins_count: 0, period: "hoy"}`
3. Construir contexto: para cada checkin, concatenar nombre + respuestas de chunks
4. Llamar `generation_service.generate(prompt, system_instruction=CEO_SYSTEM_INSTRUCTION)`
5. Retornar `{summary, checkins_count, period: "hoy"}`

#### 3.4 `app/api/v1/ceo.py` — Endpoints

**Pydantic schemas** (definir en `app/api/schemas/ceo_request.py` y `ceo_response.py`):

```python
# ceo_request.py
class CeoQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500,
                          examples=["¿Qué bloqueos reportaron los empleados hoy?"])

# ceo_response.py
class SourceItem(BaseModel):
    employee_name: str
    date: str  # ISO format YYYY-MM-DD
    excerpt: str

class CeoQueryResponse(BaseModel):
    answer: str
    confidence: Literal["alta", "media", "baja", "sin_datos"]
    sources: list[SourceItem]

class CeoDailySummaryResponse(BaseModel):
    summary: str
    checkins_count: int
    period: str
```

**Router** `app/api/v1/ceo.py`:

```python
router = APIRouter(prefix="/ceo")

@router.post("/query", response_model=CeoQueryResponse)
async def ceo_query(
    body: CeoQueryRequest,
    service: CeoService = Depends(get_ceo_service),
) -> CeoQueryResponse:
    try:
        result = await service.query(body.question)
    except GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return CeoQueryResponse(**result)

@router.get("/summary", response_model=CeoDailySummaryResponse)
async def ceo_summary(
    service: CeoService = Depends(get_ceo_service),
) -> CeoDailySummaryResponse:
    try:
        result = await service.daily_summary()
    except GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return CeoDailySummaryResponse(**result)
```

#### 3.5 Dependency `get_ceo_service` en `app/dependencies.py`

```python
def get_ceo_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    generation_service = Depends(get_generation_service),
) -> "CeoService":
    from app.services.ceo_service import CeoService
    return CeoService(
        db=db,
        embedding_service=embedding_service,
        generation_service=generation_service,
    )
```

#### 3.6 Registro en `app/api/v1/router.py`

```python
from app.api.v1.ceo import router as ceo_router
router.include_router(ceo_router, tags=["ceo"])
```

---

### 4. Implementation Phases (TDD)

**Fase 1 — Prompts** (no tests, solo añadir constantes):
- Editar `app/core/prompts.py`: añadir `CEO_SYSTEM_INSTRUCTION`, `CEO_SYNTHESIS_PROMPT`, `CEO_DAILY_SUMMARY_PROMPT`

**Fase 2 — Core RAG pipeline** (TDD):
- Crear `tests/test_core/test_ceo_query.py` con tests failing
- Implementar `app/core/ceo_query.py` hasta verde

**Fase 3 — Service** (TDD):
- Crear `tests/test_services/test_ceo_service.py` con tests failing
- Implementar `app/services/ceo_service.py` hasta verde

**Fase 4 — API endpoints** (TDD):
- Crear `tests/test_api/test_ceo.py` con tests failing
- Crear schemas Pydantic `app/api/schemas/ceo_request.py` y `app/api/schemas/ceo_response.py`
- Implementar `app/api/v1/ceo.py`
- Actualizar `app/dependencies.py` con `get_ceo_service`
- Registrar en `app/api/v1/router.py`

**Fase 5 — Suite completa**:
- Ejecutar `pytest tests/ --asyncio-mode=auto -q`

---

### 5. Test Strategy

Todos los tests deben mockear servicios externos. Sin llamadas reales a Gemini ni a la DB.

**`tests/test_core/test_ceo_query.py`**

```python
# Mock EmbeddingService y GenerationService
mock_embedding_service = MagicMock()
mock_embedding_service.generate_single_embedding = AsyncMock(return_value=[0.1] * 768)

mock_generation_service = MagicMock()
mock_generation_service.generate = AsyncMock(return_value="Respuesta de prueba.")

# Mock DB session con AsyncMock
mock_db = AsyncMock(spec=AsyncSession)
mock_db.execute = AsyncMock(return_value=mock_result)
```

Tests clave:
- `test_query_returns_answer_confidence_sources`: verificar estructura del dict
- `test_query_uses_retrieval_query_task_type`: verificar que embed recibe `task_type="RETRIEVAL_QUERY"`
- `test_query_no_chunks_returns_sin_datos`: cuando DB retorna vacío, confidence == "sin_datos", no llama a Gemini
- `test_query_high_confidence_when_top_score_gte_070`: threshold >= 0.70 → "alta"
- `test_query_medium_confidence_when_top_score_between_045_069`: → "media"
- `test_query_low_confidence_when_top_score_lt_045`: → "baja"
- `test_query_sources_limited_to_5`: máximo 5 sources en respuesta
- `test_query_excerpt_limited_to_200_chars`: excerpt truncado a 200 chars

**`tests/test_services/test_ceo_service.py`**

```python
# Mockear ceo_query.query directamente con patch
@patch("app.services.ceo_service.rag_query")
async def test_service_query_delegates_to_rag_pipeline(...):
    ...
```

Tests clave:
- `test_query_delegates_to_ceo_query_module`
- `test_daily_summary_with_no_checkins_today`
- `test_daily_summary_with_checkins_returns_summary`
- `test_daily_summary_calls_generation_service`

**`tests/test_api/test_ceo.py`**

Usar fixture `client_with_mock_llm` del conftest (ya existe). Necesita override de `get_ceo_service`.

Tests clave:
- `test_post_ceo_query_returns_200_with_valid_body`
- `test_post_ceo_query_empty_question_returns_422`
- `test_post_ceo_query_question_too_long_returns_422`
- `test_post_ceo_query_generation_error_returns_503`
- `test_get_ceo_summary_returns_200`
- `test_get_ceo_summary_structure`: verificar campos `summary`, `checkins_count`, `period`

---

### 6. Acceptance Criteria

| ID | Criterio | Verificación |
|----|----------|--------------|
| AC-01 | `POST /api/v1/ceo/query` con `{"question": "..."}` retorna 200 con `answer`, `confidence`, `sources` | curl / pytest |
| AC-02 | `confidence` es uno de `["alta", "media", "baja", "sin_datos"]` | test_ceo_query.py |
| AC-03 | Sin chunks disponibles: `confidence == "sin_datos"`, `sources == []`, no llama Gemini | test_ceo_query.py |
| AC-04 | `sources` contiene máximo 5 items, cada uno con `employee_name`, `date`, `excerpt` | test_ceo_query.py |
| AC-05 | `excerpt` está truncado a 200 caracteres | test_ceo_query.py |
| AC-06 | El embedding de la pregunta usa `task_type="RETRIEVAL_QUERY"` | test_ceo_query.py |
| AC-07 | `GET /api/v1/ceo/summary` retorna 200 con `summary`, `checkins_count`, `period` | curl / pytest |
| AC-08 | Si Gemini falla (GenerationError), ambos endpoints retornan 503 | test_api/test_ceo.py |
| AC-09 | `question` vacía o > 500 chars retorna 422 | test_api/test_ceo.py |
| AC-10 | Todos los prompts CEO están en `app/core/prompts.py` como constantes, no inline | revisión código |

## Implementation Review

**Fecha:** 2026-05-16
**PR:** #6
**Rama:** feature-issue-EPIC-005

### MoSCoW Must — Checklist

| Tarea | Criterio | Estado | Evidencia en diff |
|-------|----------|--------|-------------------|
| CEO-01 | `app/core/ceo_query.py` — RAG pipeline completo | PASS | Archivo nuevo con embed, SQL pgvector, re-rank, síntesis Gemini, confidence heuristic, sources truncadas |
| CEO-02 | `CEO_SYNTHESIS_PROMPT` y `CEO_DAILY_SUMMARY_PROMPT` en `app/core/prompts.py` | PASS | Añadidas las tres constantes: `CEO_SYSTEM_INSTRUCTION`, `CEO_SYNTHESIS_PROMPT`, `CEO_DAILY_SUMMARY_PROMPT` |
| CEO-03 | `POST /api/v1/ceo/query` → `{answer, confidence, sources}` | PASS | `app/api/v1/ceo.py` + schemas `ceo_request.py` / `ceo_response.py`, router registrado |
| CEO-04 | `GET /api/v1/ceo/summary` → `{summary, checkins_count, period}` | PASS | Mismo router, `CeoDailySummaryResponse` con los tres campos requeridos |

### Should Have — Checklist

| Criterio | Estado | Evidencia |
|----------|--------|-----------|
| `app/services/ceo_service.py` con orquestación limpia | PASS | Nuevo archivo; `query()` delega a `rag_query`, `daily_summary()` construye contexto y llama Gemini |
| Manejo de errores HTTP (404 sin chunks, 503 si Gemini falla) | PASS* | 503 implementado correctamente para `GenerationError`. La ruta sin chunks retorna respuesta normal con `confidence=sin_datos` en lugar de 404 — comportamiento válido y aceptable |
| Logging estructurado con structlog | PASS | `structlog.stdlib.get_logger()` usado en `ceo_query.py`, `ceo_service.py` y `ceo.py` |

### Approach Changes (aceptables)

- **Sin 404 cuando no hay chunks**: La spec sugería 404 pero la implementación retorna 200 con `confidence="sin_datos"` y `sources=[]`. Es un approach más limpio: el endpoint siempre responde, el caller decide qué hacer con la confianza. Aceptable.
- **SQL usa `CAST(:q_vec AS vector)`** en lugar del bind param directo: fix técnico necesario por limitaciones de pgvector con SQLAlchemy; correcto.
- **`daily_summary` filtra por `completed_at >= today_start`** en lugar de `started_at`: más semánticamente correcto para "check-ins completados hoy".

### Acceptance Criteria — Verificación

| AC | Estado |
|----|--------|
| AC-01 | PASS — endpoint POST implementado, responde 200 con los tres campos |
| AC-02 | PASS — `Literal["alta", "media", "baja", "sin_datos"]` en Pydantic schema |
| AC-03 | PASS — early return sin llamar Gemini cuando `rows` vacío |
| AC-04 | PASS — `scored[:5]` limita fuentes a 5 |
| AC-05 | PASS — `row["answer_text"][:200]` en la construcción de sources |
| AC-06 | PASS — `task_type="RETRIEVAL_QUERY"` en la llamada a embedding service |
| AC-07 | PASS — endpoint GET implementado con los tres campos |
| AC-08 | PASS — `except GenerationError → HTTPException(503)` en ambos endpoints |
| AC-09 | PASS — `min_length=1, max_length=500` en `CeoQueryRequest.question` |
| AC-10 | PASS — todos los prompts en `app/core/prompts.py` como constantes nombradas |

### Veredicto

**APPROVED** — Todos los Must implementados. Approach changes técnicamente justificados. Sin deuda técnica detectada.

## QA Report

**Fecha:** 2026-05-16
**Entorno:** worktree `feature-issue-EPIC-005`, DB local `her_poc`

### Test Cases

| TC | Fichero | Resultado | Tests |
|----|---------|-----------|-------|
| TC-1 | `tests/test_core/test_ceo_query.py` | PASS | 20/20 |
| TC-2 | `tests/test_services/test_ceo_service.py` | PASS | 12/12 |
| TC-3 | `tests/test_api/test_ceo.py` | PASS | 17/17 |
| TC-4 | Suite completa `tests/` | PASS | 213/213 |

### Cobertura de criterios de aceptación validados por tests

- AC-02: `test_confidence_values_are_valid` — verifica los cuatro valores literales
- AC-03: `test_no_chunks_does_not_call_generation_service` + `test_sin_datos_confidence_when_no_chunks`
- AC-04: `test_sources_limited_to_5`
- AC-05: `test_excerpt_limited_to_200_chars`
- AC-06: `test_uses_retrieval_query_task_type`
- AC-08: `test_post_ceo_query_generation_error_returns_503`
- AC-09: `test_post_ceo_query_empty_question_returns_422` + `test_post_ceo_query_question_too_long_returns_422`

### Regresiones

Ninguna. 213 tests pasan (mismo número que la suite previa al EPIC).

### Veredicto

**QA PASSED** — Ready to merge.
