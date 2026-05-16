# EPIC-004: Flujo de Check-in del Empleado

**Status:** open
**Espera a:** EPIC-002

## Descripción
El empleado inicia sesión, el agente conduce 4 turnos (presentación + 3 preguntas fijas). Al finalizar se vectorizan y persisten todas las respuestas.

## Preguntas fijas
| Index | Pregunta |
|-------|----------|
| 0 | "¡Hola! Soy HER. ¿Cómo te llamas?" |
| 1 | "¿En qué trabajaste hoy, {nombre}?" |
| 2 | "¿Tuviste algún bloqueo o necesitas ayuda?" |
| 3 | "¿Qué planeas hacer mañana?" |

## Tareas
- CHECKIN-01 — Crear `app/core/checkin_flow.py`
- CHECKIN-02 — Crear `app/services/checkin_service.py`
- CHECKIN-03 — Endpoint `POST /api/v1/checkin/start`
- CHECKIN-04 — Endpoint `POST /api/v1/checkin/{session_id}/answer`
- CHECKIN-05 — Endpoint `GET /api/v1/checkin/{session_id}/status`

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| CHECKIN-01 | — | — |
| CHECKIN-02 | — | CHECKIN-01 |
| CHECKIN-03 | CHECKIN-04, CHECKIN-05 | CHECKIN-02 |
| CHECKIN-04 | CHECKIN-03, CHECKIN-05 | CHECKIN-02 |
| CHECKIN-05 | CHECKIN-03, CHECKIN-04 | CHECKIN-02 |

---

## Technical Spec

**Fecha:** 2026-05-16
**Plan completo:** `.claude/doc/EPIC-004-checkin-empleado/backend.md`

### 1. Executive Summary

Implementar el flujo conversacional de check-in diario de HER: 4 turnos fijos (nombre + 3 preguntas de trabajo). El empleado interactúa texto a texto (STT no requerido en esta epic). Al completar el cuarto turno, las respuestas se vectorizan en batch con `EmbeddingService` y se persisten en `her.check_in_chunks` para su uso posterior por el CEO.

Entregables:
- `app/core/checkin_flow.py` — lógica pura de las 4 preguntas
- `app/services/checkin_service.py` — orquestación con DB y embeddings
- `app/api/v1/checkin.py` — 3 endpoints REST
- Schemas Pydantic v2 para request/response
- Suite TDD completa (unit + integración + API)

### 2. Problem Statement

#### Estado actual

- Las tablas `her.employees`, `her.check_ins`, `her.check_in_chunks` existen desde EPIC-002 con sus índices HNSW.
- `EmbeddingService` (google-genai, 768d) está listo en `app/core/embeddings.py`.
- No existe ningún código de flujo conversacional ni endpoints de check-in.
- No existe el directorio `app/services/`.

#### Gap a cubrir

Sin esta epic, no hay forma de iniciar una sesión de check-in, recoger respuestas, ni vectorizar el contenido de los empleados. El CEO Dashboard (epics futuras) no tiene datos que consultar.

### 3. MoSCoW

#### Must Have
- `POST /api/v1/checkin/start` — crear sesión y devolver primera pregunta
- `POST /api/v1/checkin/{session_id}/answer` — procesar respuesta y avanzar el turno
- `GET /api/v1/checkin/{session_id}/status` — estado de la sesión
- Flujo completo de 4 turnos con interpolación del nombre en la pregunta 1
- Vectorización batch de los 4 chunks al completar (usando `EmbeddingService`)
- Persistencia de `Employee`, `CheckIn`, `CheckInChunk` en schema `her`

#### Should Have
- Manejo de sesión ya completada (409 Conflict)
- Respuesta `employee_name` en el endpoint `/answer` al completar
- Tests unitarios para `checkin_flow.py` (sin DB)
- Tests de integración con mock de `EmbeddingService`

#### Could Have
- Lookup de empleado existente por nombre (evitar duplicados)
- Validación de `answer_text` mínimo (longitud)

#### Won't Have (en esta epic)
- Integración con STT/TTS (EPIC-003 — el frontend ya transcribe)
- Endpoint para listar sesiones del empleado
- Cancelación de sesión en curso
- Webhook o notificación al completar

### 4. Technical Design

#### 4.1 `app/core/checkin_flow.py`

Módulo puro sin dependencias externas (no importa `app.models`, `app.db`, `app.core.embeddings`).

```python
QUESTIONS: list[str] = [
    "¡Hola! Soy HER. ¿Cómo te llamas?",
    "¿En qué trabajaste hoy, {name}?",
    "¿Tuviste algún bloqueo o necesitas ayuda?",
    "¿Qué planeas hacer mañana?",
]

TOTAL_QUESTIONS: int = 4


def get_question(index: int, name: str = "") -> str:
    """Devuelve la pregunta interpolando {name} si aplica.

    Raises IndexError si index < 0 o index >= TOTAL_QUESTIONS.
    """
    if index < 0 or index >= TOTAL_QUESTIONS:
        raise IndexError(f"Question index {index} out of range [0, {TOTAL_QUESTIONS})")
    return QUESTIONS[index].format(name=name)


def is_complete(index: int) -> bool:
    """True si index >= TOTAL_QUESTIONS. Llamar con el índice POST-respuesta."""
    return index >= TOTAL_QUESTIONS
```

Notas:
- `QUESTIONS[1]` usa `{name}` — `str.format(name="")` devuelve `"¿En qué trabajaste hoy, ?"` si no hay nombre. El implementador puede usar `name or "compañero"` para mayor naturalidad.
- `is_complete` se llama con `current_index + 1` después de guardar la respuesta.

#### 4.2 `app/services/checkin_service.py`

**`CheckInService.__init__(self, db: AsyncSession, embedding_service: EmbeddingService)`**

**`async create_session() -> tuple[CheckIn, str]`**

Flujo:
1. Generar `session_id = str(uuid.uuid4())`.
2. Resolver la FK `employee_id` (ver decisión de FK nullable en §4.5).
3. Crear `CheckIn(session_id=session_id, status="in_progress", employee_id=...)`.
4. `db.add(checkin)` + `await db.flush()`.
5. Devolver `(checkin, get_question(0))`.

**`async process_answer(session_id: str, answer_text: str) -> tuple[str | None, bool, str | None]`**

Retorna `(next_question_text, is_complete, employee_name)`.

Flujo:
1. `SELECT CheckIn WHERE session_id=... WITH selectinload(chunks) AND selectinload(employee)`.
2. Si no existe → lanzar excepción de "not found".
3. Si `status == "completed"` → lanzar excepción de "already completed".
4. `current_index = len(checkin.chunks)`.
5. `question_text = get_question(current_index, name=checkin.employee.name)`.
6. Crear y añadir `CheckInChunk(checkin_id=checkin.id, question_index=current_index, question_text=question_text, answer_text=answer_text.strip())`.
7. Si `current_index == 0`: `checkin.employee.name = answer_text.strip()`.
8. `next_index = current_index + 1`.
9. Si `is_complete(next_index)`:
   - Llamar `await self.complete_session(session_id)`.
   - Devolver `(None, True, checkin.employee.name)`.
10. Si no:
    - Devolver `(get_question(next_index, name=checkin.employee.name), False, None)`.

**`async complete_session(session_id: str) -> None`**

Flujo:
1. Obtener `CheckIn` con `selectinload(CheckIn.chunks)`.
2. Filtrar chunks con `embedding is None`, extraer `answer_text`.
3. `embeddings = await self._embedding_service.generate_embeddings(texts, task_type="RETRIEVAL_DOCUMENT")`.
4. Asignar embedding a cada chunk.
5. `checkin.status = "completed"`, `checkin.completed_at = datetime.now(UTC)`.
6. `await db.flush()`.

**`async get_session_status(session_id: str) -> CheckIn`**

Retorna el `CheckIn` con `selectinload(CheckIn.chunks)` y `selectinload(CheckIn.employee)`.

#### 4.3 Endpoints

**`POST /api/v1/checkin/start`**

```
Response 200:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "question_text": "¡Hola! Soy HER. ¿Cómo te llamas?"
}
```

**`POST /api/v1/checkin/{session_id}/answer`**

```
Request body:
{
  "answer_text": "Soy María García"
}

Response 200 (turno intermedio):
{
  "next_question_text": "¿En qué trabajaste hoy, María García?",
  "is_complete": false,
  "employee_name": null
}

Response 200 (último turno):
{
  "next_question_text": null,
  "is_complete": true,
  "employee_name": "María García"
}

Response 404: session_id no existe
Response 409: sesión ya completada
Response 503: EmbeddingError al vectorizar
```

**`GET /api/v1/checkin/{session_id}/status`**

```
Response 200:
{
  "session_id": "550e8400-...",
  "status": "completed",
  "questions_answered": 4,
  "employee_name": "María García"
}

Response 404: session_id no existe
```

#### 4.4 Schemas Pydantic v2

**`app/api/schemas/checkin_request.py`**

```python
class AnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=2000)
```

**`app/api/schemas/checkin_response.py`**

```python
class StartCheckInResponse(BaseModel):
    session_id: str
    question_text: str

class AnswerCheckInResponse(BaseModel):
    next_question_text: str | None
    is_complete: bool
    employee_name: str | None

class CheckInStatusResponse(BaseModel):
    session_id: str
    status: str
    questions_answered: int
    employee_name: str
```

#### 4.5 Decisión FK nullable — Migración 010 (recomendada)

`CheckIn.employee_id` es `NOT NULL` en migración 008. Para poder crear una sesión antes de conocer el nombre del empleado, se recomienda añadir:

**`alembic/versions/010_make_checkin_employee_id_nullable.py`**

```python
revision: str = "010"
down_revision: str | None = "009"

def upgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=True, schema="her")
    # También actualizar el modelo SQLAlchemy: employee_id: Mapped[uuid.UUID | None]

def downgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=False, schema="her")
```

Sin esta migración, la alternativa es crear un `Employee` placeholder en `create_session` y actualizarlo en la respuesta al índice 0.

#### 4.6 Modificaciones a archivos existentes

| Archivo | Cambio |
|---------|--------|
| `app/dependencies.py` | Añadir `get_checkin_service()` al final (import lazy) |
| `app/api/v1/router.py` | `from app.api.v1.checkin import router as checkin_router` + `router.include_router(checkin_router)` |

**Patrón `get_checkin_service` en `app/dependencies.py`:**

```python
def get_checkin_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> "CheckInService":
    from app.services.checkin_service import CheckInService
    return CheckInService(db=db, embedding_service=embedding_service)
```

### 5. Implementation Phases (TDD)

**Phase 1 — Core (CHECKIN-01)**

1. Escribir `tests/test_core/test_checkin_flow.py` (10 tests, todos en rojo).
2. Implementar `app/core/checkin_flow.py`.
3. Verificar verde: `pytest tests/test_core/test_checkin_flow.py`.

**Phase 2 — Service (CHECKIN-02)**

1. Si Opción B: escribir e implementar migración 010.
2. Escribir `tests/test_services/test_checkin_service.py` (10 tests, todos en rojo).
3. Implementar `app/services/__init__.py` + `app/services/checkin_service.py`.
4. Verificar verde: `pytest tests/test_services/test_checkin_service.py`.

**Phase 3 — Endpoints (CHECKIN-03/04/05)**

1. Escribir `tests/test_api/test_checkin.py` (8 tests, todos en rojo).
2. Crear schemas en `app/api/schemas/`.
3. Implementar `app/api/v1/checkin.py`.
4. Modificar `app/dependencies.py` y `app/api/v1/router.py`.
5. Verificar verde: `pytest tests/test_api/test_checkin.py`.

**Phase 4 — Suite completa**

```bash
pytest tests/ --asyncio-mode=auto -v
```

Todos los tests previos (embeddings, generation, search, health) deben seguir pasando.

### 6. Test Strategy

#### Mocks para EmbeddingService

Seguir el patrón de `conftest.py` existente (`_make_mock_embedding_service`):

```python
def _make_mock_checkin_embedding_service() -> MagicMock:
    service = MagicMock()
    service.generate_embeddings = AsyncMock(
        side_effect=lambda texts, task_type="RETRIEVAL_DOCUMENT": [[0.1] * 768 for _ in texts]
    )
    return service
```

Para los tests de API, añadir en `conftest.py`:

```python
@pytest.fixture
async def client_for_checkin() -> AsyncIterator[AsyncClient]:
    from app.db import init_db
    from app.dependencies import get_checkin_service, get_embedding_service
    from app.main import app
    from app.services.checkin_service import CheckInService

    test_settings = get_test_settings()
    init_db(test_settings)
    mock_emb = _make_mock_embedding_service()

    # Limpiar tablas her.* antes de cada test
    engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(sa_text("DELETE FROM her.check_in_chunks"))
        await conn.execute(sa_text("DELETE FROM her.check_ins"))
        await conn.execute(sa_text("DELETE FROM her.employees"))
    await engine.dispose()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_embedding_service] = lambda: mock_emb

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

#### Niveles de test

| Nivel | Archivo | Mock | Requiere DB |
|-------|---------|------|-------------|
| Unit | `test_checkin_flow.py` | Ninguno | No |
| Integration | `test_checkin_service.py` | EmbeddingService | Sí (her_poc) |
| API | `test_checkin.py` | EmbeddingService + get_embedding_service | Sí (her_poc) |

### 7. Acceptance Criteria

| AC | Criterio | Verificación |
|----|----------|-------------|
| AC-1 | `POST /start` devuelve `session_id` (UUID string) y `question_text` = pregunta 0 | `pytest test_checkin.py::test_start_returns_session_id_and_question` |
| AC-2 | 4 respuestas consecutivas completan la sesión (`is_complete=True`) | `pytest test_checkin.py::test_full_flow_integration` |
| AC-3 | La pregunta 1 incluye el nombre dado en la respuesta 0 | `pytest test_checkin.py::test_answer_returns_next_question` |
| AC-4 | Al completar, los 4 chunks tienen `embedding` != None en DB | `pytest test_checkin_service.py::test_complete_session_generates_embeddings` |
| AC-5 | `GET /status` con sesión completada devuelve `status="completed"` y `questions_answered=4` | `pytest test_checkin.py::test_status_returns_questions_answered` |
| AC-6 | `POST /{id}/answer` con session_id inexistente → HTTP 404 | `pytest test_checkin.py::test_answer_unknown_session_returns_404` |
| AC-7 | `POST /{id}/answer` en sesión ya completada → HTTP 409 | `pytest test_checkin.py::test_answer_completed_session_returns_409` |
| AC-8 | Suite completa `pytest tests/` pasa sin regresiones en search/health | CI verde |

### 8. Appendix

#### Estructura de archivos resultante (worktree EPIC-004)

```
app/
  core/
    checkin_flow.py          [NUEVO]
    embeddings.py            [existente]
    generation.py            [existente]
    prompts.py               [existente]
    ranking.py               [existente]
    retrieval.py             [existente]
  services/
    __init__.py              [NUEVO]
    checkin_service.py       [NUEVO]
  api/
    schemas/
      checkin_request.py     [NUEVO]
      checkin_response.py    [NUEVO]
      common.py              [existente]
      search_request.py      [existente]
      search_response.py     [existente]
    v1/
      checkin.py             [NUEVO]
      health.py              [existente]
      router.py              [MODIFICAR]
      search.py              [existente]
  models/
    employee.py              [existente, EPIC-002]
    checkin.py               [existente, EPIC-002]
    checkin_chunk.py         [existente, EPIC-002]
    base.py                  [existente]
    chunk.py                 [existente]
  dependencies.py            [MODIFICAR]
  config.py                  [sin cambios]
  db.py                      [sin cambios]
  main.py                    [sin cambios]
alembic/
  versions/
    010_make_checkin_employee_id_nullable.py  [NUEVO, si Opción B]

tests/
  test_core/
    test_checkin_flow.py     [NUEVO]
  test_services/
    __init__.py              [NUEVO]
    test_checkin_service.py  [NUEVO]
  test_api/
    test_checkin.py          [NUEVO]
  conftest.py                [MODIFICAR: añadir client_for_checkin fixture]
```

#### Dependencias externas

No se añaden nuevas dependencias a `pyproject.toml`. Todo utiliza:
- `sqlalchemy[asyncio]` + `asyncpg` (ya presentes)
- `pgvector` (ya presente)
- `google-genai` (ya presente, EPIC-001)
- `fastapi` + `pydantic` (ya presentes)
- `structlog` (ya presente)

#### Relación con epics futuras

- **EPIC-003 (Speech):** Los endpoints de check-in reciben `answer_text` como string plano. El frontend usa STT para transcribir antes de llamar a `/answer`. No hay dependencia en ninguna dirección.
- **EPIC-005+ (CEO Dashboard):** Consumirá `her.check_in_chunks` via búsqueda vectorial en `her.*` schema. Los embeddings generados aquí son la fuente de datos.

## Implementation Review

**Status:** ready-to-merge
**Fecha:** 2026-05-16
**Revisor:** review-spec automatizado
**Veredicto:** ✅ Apto para QA

### Cobertura de Must Have

| Must | Estado | Evidencia |
|------|--------|-----------|
| `POST /api/v1/checkin/start` — crear sesión y devolver primera pregunta | ✅ | `app/api/v1/checkin.py` — `start_checkin()`, devuelve `session_id` + `question_text` |
| `POST /api/v1/checkin/{session_id}/answer` — procesar respuesta y avanzar turno | ✅ | `app/api/v1/checkin.py` — `answer_checkin()`, 404/409/503 correctos |
| `GET /api/v1/checkin/{session_id}/status` — estado de la sesión | ✅ | `app/api/v1/checkin.py` — `checkin_status()`, 404 correcto |
| Flujo completo 4 turnos con interpolación del nombre en pregunta 1 | ✅ | `app/core/checkin_flow.py` — `get_question(1, name=...)` con fallback "compañero" |
| Vectorización batch de los 4 chunks al completar (EmbeddingService) | ✅ | `checkin_service.py::complete_session` — batch embeddings + `chunk.embedding = embedding` |
| Persistencia de `Employee`, `CheckIn`, `CheckInChunk` en schema `her` | ✅ | `checkin_service.py::create_session` — Employee placeholder + CheckIn; chunks en `process_answer` |

### Should Have

| Should | Estado |
|--------|--------|
| Manejo de sesión ya completada (409 Conflict) | ✅ `SessionAlreadyCompletedError` → HTTP 409 |
| Respuesta `employee_name` en `/answer` al completar | ✅ `AnswerCheckInResponse.employee_name` poblado en último turno |
| Tests unitarios `test_checkin_flow.py` (sin DB) | ✅ 12 casos cubriendo todos los índices, errores y `is_complete` |
| Tests integración con mock de `EmbeddingService` | ✅ `test_checkin_service.py` (10 casos) + `test_checkin.py` (8 casos API) |

### Desviaciones aceptables

- **Migración 010 (`employee_id` nullable):** entregada y alineada con Opción B de la spec — correcto.
- **`app/models/checkin.py` actualizado** a `employee_id: Mapped[uuid.UUID | None]` para reflejar la migración — correcto.
- **`get_db_session` con `session.begin()`** (auto-commit en contexto): cambio transversal correcto, fuera de spec pero necesario para que los tests de integración funcionen sin commit explícito.
- **Employee placeholder con `name=""`** creado en `create_session` (Opción B de spec §4.2) en lugar de `employee_id` nullable — implementación más robusta que evitar FK null.
- **`_db.refresh(checkin, ["chunks", "employee"])`** en `_get_checkin_with_relations` — correcto para evitar stale identity-map cache entre turnos consecutivos en la misma sesión.

## QA Report

**Fecha:** 2026-05-16
**QA Agent:** qa-acceptance
**Worktree:** `.trees/feature-issue-EPIC-004`
**Veredicto:** PASSED — Ready to merge

### Validation Report

Passed:
- TC-1 (test_checkin_flow.py): 12/12 tests passed — pure unit tests, no DB dependency
- TC-2 (test_checkin_service.py): 12/12 tests passed — service integration with mock EmbeddingService
- TC-3 (test_checkin.py): 9/9 tests passed — API endpoint tests covering all AC
- TC-4 (test_full_flow_integration): PASSED — full 4-turn start→answer×4→status=completed flow confirmed
- TC-5 (full suite): 147 passed, 3 skipped, 0 failures — no regressions in search/health/embeddings/generation/models
- TC-6 (migration 010): head revision confirmed as `010 — Make her.check_ins.employee_id nullable`

Warnings (non-blocking):
- `SAWarning: transaction already deassociated from connection` in `test_her_models.py::test_employee_name_not_null` and `test_checkin_session_id_unique` — pre-existing issue from EPIC-002 test cleanup, not introduced by EPIC-004

### Acceptance Criteria Coverage

| AC | Criterio | Test | Resultado |
|----|----------|------|-----------|
| AC-1 | `POST /start` devuelve `session_id` (UUID string) y `question_text` = pregunta 0 | `test_start_returns_session_id_and_question` | PASSED |
| AC-2 | 4 respuestas consecutivas completan la sesión (`is_complete=True`) | `test_full_flow_integration` | PASSED |
| AC-3 | La pregunta 1 incluye el nombre dado en la respuesta 0 | `test_answer_returns_next_question` | PASSED |
| AC-4 | Al completar, los 4 chunks tienen `embedding` != None en DB | `test_complete_session_generates_embeddings` | PASSED |
| AC-5 | `GET /status` con sesión completada devuelve `status="completed"` y `questions_answered=4` | `test_status_returns_questions_answered` | PASSED |
| AC-6 | `POST /{id}/answer` con session_id inexistente → HTTP 404 | `test_answer_unknown_session_returns_404` | PASSED |
| AC-7 | `POST /{id}/answer` en sesión ya completada → HTTP 409 | `test_answer_completed_session_returns_409` | PASSED |
| AC-8 | Suite completa `pytest tests/` pasa sin regresiones en search/health | 147 passed, 3 skipped | PASSED |

### TC Classification

| TC | Descripcion | Tipo | Motivo |
|----|-------------|------|--------|
| TC-1 | Unit tests checkin_flow.py | Paralelo | Sin DB, sin estado compartido |
| TC-2 | Service tests CheckInService | Paralelo | Mock EmbeddingService, DB limpiada por fixture |
| TC-3 | API endpoint tests | Paralelo | ASGI transport, DB limpiada por `client_for_checkin` fixture |
| TC-4 | Flujo completo 4 turnos | Secuencial | Subtset de TC-3, mismo fixture |
| TC-5 | Suite completa sin regresiones | Secuencial | Ejecutar tras TC-1/TC-2/TC-3 para confirmar ausencia de regresiones |
| TC-6 | Migracion 010 aplicada | Paralelo | Consulta de estado, sin escritura |

### Observaciones

- La advertencia `SAWarning: transaction already deassociated from connection` es pre-existente (EPIC-002) y no afecta la funcionalidad. Se documenta como deuda técnica menor.
- El comando `alembic current` no muestra la revision en este entorno porque la tabla `her.alembic_version` queda vacía tras el teardown del fixture de tests (que corre `alembic downgrade base` + `alembic upgrade head` por sesion). La revision `010` está confirmada como `head` via `alembic heads` y `alembic history`.
- Los 3 tests skipped corresponden a tests de modelos marcados con `pytest.mark.skip` desde EPIC-002 — no son regresiones de esta epic.

**Report completo:** `.claude/doc/EPIC-004-checkin-empleado/qa-report.md`
