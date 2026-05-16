# Backend Plan: EPIC-004 — Flujo de Check-in del Empleado

**Fecha:** 2026-05-16
**Status:** plan listo, pendiente implementación
**Worktree:** `.trees/feature-issue-EPIC-004`

---

## 1. Context

### Baseline del worktree EPIC-004

El worktree `.trees/feature-issue-EPIC-004` ya incluye los cambios de EPIC-001 y EPIC-002:

- `app/models/employee.py` — `Employee` con `HerBase` (schema `her`)
- `app/models/checkin.py` — `CheckIn` con session_id unique, status, started_at, completed_at
- `app/models/checkin_chunk.py` — `CheckInChunk` con `Vector(768)`, question_index (0-3)
- `app/core/embeddings.py` — `EmbeddingService` con `google-genai`, 768 dims, batch support
- `app/models/__init__.py` — exporta `Employee`, `CheckIn`, `CheckInChunk`, `HerBase`
- Migraciones 006-009 ya presentes

No existe ninguno de estos archivos todavía:
- `app/core/checkin_flow.py`
- `app/services/checkin_service.py`
- `app/api/v1/checkin.py`
- `app/api/schemas/checkin_request.py`
- `app/api/schemas/checkin_response.py`
- `app/services/__init__.py`

### Modelos ORM relevantes (leídos de EPIC-002)

```python
# HerBase está en app/models/employee.py — NO en app/models/base.py
class HerBase(DeclarativeBase):
    metadata = MetaData(schema="her")

class Employee(HerBase):
    __tablename__ = "employees"
    id: UUID (PK, uuid_generate_v4)
    name: Text NOT NULL
    created_at: TIMESTAMP WITH TIME ZONE
    checkins: relationship -> CheckIn

class CheckIn(HerBase):
    __tablename__ = "check_ins"
    id: UUID (PK)
    employee_id: UUID FK(her.employees.id, CASCADE)
    session_id: String UNIQUE INDEX
    status: String(20) DEFAULT 'in_progress'  # in_progress | completed | failed
    started_at: TIMESTAMP WITH TIME ZONE
    completed_at: TIMESTAMP WITH TIME ZONE nullable
    employee: relationship -> Employee
    chunks: relationship -> CheckInChunk

class CheckInChunk(HerBase):
    __tablename__ = "check_in_chunks"
    id: UUID (PK)
    checkin_id: UUID FK(her.check_ins.id, CASCADE)
    question_index: Integer NOT NULL  # 0, 1, 2, 3
    question_text: Text NOT NULL
    answer_text: Text NOT NULL
    embedding: Vector(768) nullable
    created_at: TIMESTAMP WITH TIME ZONE
    checkin: relationship -> CheckIn
```

---

## 2. Archivos a crear

### CHECKIN-01: `app/core/checkin_flow.py`

```python
"""Lógica pura del flujo de check-in de 4 turnos.

No depende de base de datos ni de servicios externos.
Importable desde tests sin ninguna dependencia externa.
"""

QUESTIONS: list[str] = [
    "¡Hola! Soy HER. ¿Cómo te llamas?",
    "¿En qué trabajaste hoy, {name}?",
    "¿Tuviste algún bloqueo o necesitas ayuda?",
    "¿Qué planeas hacer mañana?",
]

TOTAL_QUESTIONS: int = len(QUESTIONS)  # 4


def get_question(index: int, name: str = "") -> str:
    """Devuelve la pregunta para el índice dado, interpolando {name} si corresponde.

    Args:
        index: Índice de la pregunta (0-3).
        name: Nombre del empleado, usado en la pregunta 1 (index=1).

    Returns:
        Texto de la pregunta con {name} reemplazado si aplica.

    Raises:
        IndexError: Si index está fuera del rango [0, TOTAL_QUESTIONS).
    """
    if index < 0 or index >= TOTAL_QUESTIONS:
        raise IndexError(f"Question index {index} out of range [0, {TOTAL_QUESTIONS})")
    return QUESTIONS[index].format(name=name)


def is_complete(index: int) -> bool:
    """Devuelve True si el índice alcanzó o supera el total de preguntas.

    Se llama DESPUÉS de incrementar el índice (post-respuesta).
    """
    return index >= TOTAL_QUESTIONS
```

Notas de implementación:
- Módulo puro (sin imports de `app.models`, `app.db`, `app.core.embeddings`).
- `QUESTIONS[1]` usa `{name}` — `str.format(name=name)` con `name=""` devuelve la cadena sin cambios para el índice 0 (la pregunta de presentación no la usa).
- No lanzar `ValueError` para name vacío — es intencional para el índice 0.

---

### CHECKIN-02: `app/services/__init__.py`

Archivo vacío. Crear antes de `checkin_service.py`.

---

### CHECKIN-02: `app/services/checkin_service.py`

```python
"""Orquestación de la sesión de check-in.

Responsabilidades:
- Crear sesiones (CheckIn) con employee lookup o creación.
- Persistir respuestas como CheckInChunk.
- Generar embeddings para todos los chunks al completar.
- Actualizar estado del CheckIn.
"""
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.checkin_flow import QUESTIONS, get_question, is_complete
from app.core.embeddings import EmbeddingService
from app.models.checkin import CheckIn
from app.models.checkin_chunk import CheckInChunk
from app.models.employee import Employee

logger = structlog.stdlib.get_logger()


class CheckInService:
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._db = db
        self._embedding_service = embedding_service

    async def create_session(self) -> tuple[CheckIn, str]:
        """Crea un nuevo CheckIn con session_id único y devuelve la primera pregunta."""
        ...

    async def process_answer(
        self,
        session_id: str,
        answer_text: str,
    ) -> tuple[str | None, bool, str | None]:
        """Procesa una respuesta, persiste el chunk, devuelve (next_question, is_complete, employee_name)."""
        ...

    async def complete_session(self, session_id: str) -> None:
        """Genera embeddings para todos los chunks y cierra la sesión."""
        ...

    async def get_session_status(self, session_id: str) -> CheckIn:
        """Recupera la sesión con sus chunks cargados."""
        ...
```

#### Lógica detallada de `create_session`

1. Generar `session_id = str(uuid.uuid4())`.
2. Crear `CheckIn(session_id=session_id, status="in_progress")` — sin employee_id todavía. El empleado se descubrirá en la primera respuesta (pregunta de nombre, index=0).
3. `db.add(checkin)` y `await db.flush()` para obtener el ID.
4. Devolver `(checkin, get_question(0))`.

**Nota crítica sobre employee_id nullable:** El modelo actual `CheckIn.employee_id` es `nullable=False`. Hay dos opciones:

- **Opción A (recomendada):** Crear un `Employee` placeholder con `name="unknown"` y actualizar el nombre en la respuesta del índice 0. Esto evita tocar el schema.
- **Opción B:** Añadir migración para hacer `employee_id` nullable hasta que se conozca el nombre.

Se recomienda la **Opción A** para no requerir migración adicional. Ver sección de Alembic.

#### Lógica detallada de `process_answer`

1. Obtener `CheckIn` por `session_id` con `selectinload(CheckIn.chunks)` y `selectinload(CheckIn.employee)`.
2. Si no existe → `HTTPException(404)` (lanzar desde el endpoint, no desde el service — devolver `None` o usar excepción propia).
3. Si status == "completed" → error (ya terminado).
4. Calcular `current_index = len(checkin.chunks)` (0 antes de la primera respuesta).
5. Obtener `question_text = get_question(current_index, name=checkin.employee.name)`.
6. Crear `CheckInChunk(checkin_id=checkin.id, question_index=current_index, question_text=question_text, answer_text=answer_text)`.
7. `db.add(chunk)`.
8. Si `current_index == 0`: actualizar `checkin.employee.name = answer_text.strip()`.
9. `next_index = current_index + 1`.
10. Si `is_complete(next_index)`:
    - Llamar `await self.complete_session(session_id)` — genera embeddings y completa.
    - Devolver `(None, True, checkin.employee.name)`.
11. Si no:
    - Devolver `(get_question(next_index, name=checkin.employee.name), False, None)`.

**Nota sobre transacciones:** Todo `process_answer` debe correr dentro de una transacción implícita. El endpoint usará `async with session.begin()` o dejará que FastAPI maneje el commit. Ver sección de dependencias.

#### Lógica detallada de `complete_session`

1. Obtener `CheckIn` con `selectinload(CheckIn.chunks)`.
2. Extraer todos los `answer_text` de los chunks con `embedding is None`.
3. Llamar `embedding_service.generate_embeddings(texts, task_type="RETRIEVAL_DOCUMENT")`.
4. Asignar cada embedding al chunk correspondiente.
5. Actualizar `checkin.status = "completed"` y `checkin.completed_at = datetime.now(UTC)`.
6. `await db.flush()` — el commit lo hace el caller (el transaction manager del endpoint).

---

### CHECKIN-03/04/05: `app/api/schemas/checkin_request.py`

```python
from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    answer_text: str = Field(
        min_length=1,
        max_length=2000,
        description="Respuesta del empleado a la pregunta actual.",
        examples=["Trabajé en el módulo de autenticación."],
    )
```

---

### CHECKIN-03/04/05: `app/api/schemas/checkin_response.py`

```python
import uuid
from pydantic import BaseModel


class StartCheckInResponse(BaseModel):
    session_id: str
    question_text: str


class AnswerCheckInResponse(BaseModel):
    next_question_text: str | None
    is_complete: bool
    employee_name: str | None


class CheckInStatusResponse(BaseModel):
    session_id: str
    status: str  # in_progress | completed | failed
    questions_answered: int
    employee_name: str
```

---

### CHECKIN-03/04/05: `app/api/v1/checkin.py`

```python
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.checkin_request import AnswerRequest
from app.api.schemas.checkin_response import (
    AnswerCheckInResponse,
    CheckInStatusResponse,
    StartCheckInResponse,
)
from app.api.schemas.common import ErrorResponse
from app.core.embeddings import EmbeddingError
from app.dependencies import get_checkin_service
from app.services.checkin_service import CheckInService

router = APIRouter(prefix="/checkin", tags=["checkin"])
logger = structlog.stdlib.get_logger()


@router.post(
    "/start",
    response_model=StartCheckInResponse,
    responses={503: {"model": ErrorResponse}},
)
async def start_checkin(
    service: CheckInService = Depends(get_checkin_service),
) -> StartCheckInResponse:
    ...


@router.post(
    "/{session_id}/answer",
    response_model=AnswerCheckInResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def answer_checkin(
    session_id: str,
    body: AnswerRequest,
    service: CheckInService = Depends(get_checkin_service),
) -> AnswerCheckInResponse:
    ...


@router.get(
    "/{session_id}/status",
    response_model=CheckInStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_checkin_status(
    session_id: str,
    service: CheckInService = Depends(get_checkin_service),
) -> CheckInStatusResponse:
    ...
```

Manejo de errores por endpoint:

| Endpoint | Condición | HTTP |
|----------|-----------|------|
| `/start` | EmbeddingError al crear (no debería ocurrir aquí) | 503 |
| `/{id}/answer` | session_id no encontrado | 404 |
| `/{id}/answer` | status == "completed" | 409 |
| `/{id}/answer` | EmbeddingError al completar | 503 |
| `/{id}/status` | session_id no encontrado | 404 |

---

## 3. Archivos a modificar

### `app/dependencies.py`

Añadir al final:

```python
def get_checkin_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> "CheckInService":
    from app.services.checkin_service import CheckInService
    return CheckInService(db=db, embedding_service=embedding_service)
```

El import lazy dentro de la función evita el import circular (pattern existente en `get_retrieval_service` y `get_generation_service`).

---

### `app/api/v1/router.py`

```python
from app.api.v1.checkin import router as checkin_router

router.include_router(checkin_router, tags=["checkin"])
```

Nota: `checkin_router` ya lleva `prefix="/checkin"` definido en el propio archivo; no añadirlo en `include_router`.

---

### `app/models/__init__.py` (en worktree EPIC-004)

Si el worktree ya tiene el `__init__.py` de EPIC-002, no hay cambio requerido. Si no, verificar que `Employee`, `CheckIn`, `CheckInChunk`, `HerBase` estén exportados.

---

## 4. Alembic — Decisiones de migración

### No se requiere nueva migración

Las tablas `her.employees`, `her.check_ins`, `her.check_in_chunks` ya existen desde las migraciones 006-009 de EPIC-002, que están presentes en el worktree EPIC-004.

### Problema: employee_id NOT NULL en create_session

El modelo `CheckIn.employee_id` es `nullable=False` (migración 008). En `create_session` aún no conocemos el nombre del empleado.

**Solución adoptada (Opción A — sin migración nueva):**

1. En `create_session`: hacer `SELECT` de un `Employee` con `name="__pending__"` o crear uno nuevo con ese placeholder.
2. En `process_answer` (index=0): actualizar `employee.name = answer_text.strip()` y opcionalmente hacer upsert si el nombre ya existe.

**Alternativa — Opción B (con migración):** Añadir migración `010_make_employee_id_nullable.py`:

```python
def upgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=True, schema="her")

def downgrade() -> None:
    op.alter_column("check_ins", "employee_id", nullable=False, schema="her")
```

La Opción B es más limpia semánticamente. Decisión final queda al implementador, pero la **spec recomienda Opción B** para mantener integridad semántica (una sesión puede comenzar antes de conocer el empleado).

---

## 5. Patrones de transacción

El `get_db_session` existente devuelve una sesión sin autocommit:

```python
async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

`async_sessionmaker` en `db.py` usa `expire_on_commit=False`. Las sesiones de SQLAlchemy async **no tienen autocommit** por defecto.

Para `process_answer` y `complete_session`, que hacen múltiples escrituras, el commit debe hacerse explícitamente. Opciones:

**Opción recomendada:** Usar `async with self._db.begin()` dentro del service para operaciones atómicas. Equivalente al patrón existente en `retrieval.py`:

```python
async with self._db.begin():
    # todas las operaciones de escritura aquí
```

Si el endpoint no gestiona transacción, el service debe hacerlo. El patrón en `retrieval.py` usa `async with self._db.begin()` para el bloque SET LOCAL + query, que es el modelo a seguir.

---

## 6. Archivos de tests a crear

### `tests/test_core/test_checkin_flow.py`

Tests unitarios puros (sin DB, sin mocks):

| Test | Descripción |
|------|-------------|
| `test_get_question_index_0` | Devuelve "¡Hola! Soy HER. ¿Cómo te llamas?" |
| `test_get_question_index_1_with_name` | Interpola nombre en pregunta 1 |
| `test_get_question_index_1_empty_name` | Sin nombre devuelve pregunta con `{name}` vacío |
| `test_get_question_index_2` | Devuelve pregunta sobre bloqueos |
| `test_get_question_index_3` | Devuelve pregunta sobre mañana |
| `test_get_question_out_of_range` | IndexError para index < 0 o >= 4 |
| `test_is_complete_false_for_0_to_3` | False para index 0, 1, 2, 3 |
| `test_is_complete_true_for_4` | True para index 4 |
| `test_is_complete_true_for_greater` | True para index > 4 |
| `test_total_questions_is_4` | `TOTAL_QUESTIONS == 4` |

### `tests/test_services/test_checkin_service.py`

Tests de integración con DB real (fixture `db_session` del conftest):

| Test | Descripción |
|------|-------------|
| `test_create_session_returns_checkin_and_first_question` | CheckIn creado, status=in_progress, pregunta 0 devuelta |
| `test_create_session_generates_unique_session_ids` | Dos llamadas → session_ids distintos |
| `test_process_answer_index_0_sets_employee_name` | Respuesta al nombre actualiza employee.name |
| `test_process_answer_index_0_returns_next_question` | Devuelve pregunta 1 con nombre interpolado |
| `test_process_answer_creates_chunk` | CheckInChunk persiste con question_index correcto |
| `test_process_answer_index_3_completes_session` | Cuarta respuesta → is_complete=True |
| `test_complete_session_generates_embeddings` | Todos los chunks tienen embedding != None |
| `test_complete_session_updates_status` | status="completed", completed_at != None |
| `test_process_answer_session_not_found` | Lanza excepción apropiada |
| `test_process_answer_already_completed` | Lanza excepción apropiada |

Mock de `EmbeddingService` siguiendo patrón de `conftest.py`:

```python
# En conftest.py añadir o en el propio test file:
def _make_mock_embedding_service() -> MagicMock:
    service = MagicMock()
    service.generate_embeddings = AsyncMock(
        side_effect=lambda texts, task_type="RETRIEVAL_DOCUMENT": [[0.1] * 768 for _ in texts]
    )
    return service
```

### `tests/test_api/test_checkin.py`

Tests de endpoints con `client_with_mock_embeddings`:

| Test | Descripción |
|------|-------------|
| `test_start_returns_session_id_and_question` | POST /start → 200, session_id y question_text presentes |
| `test_answer_returns_next_question` | POST /answer primer turno → next_question_text != None |
| `test_answer_completes_after_4_answers` | 4 respuestas seguidas → is_complete=True |
| `test_answer_unknown_session_returns_404` | Session inexistente → 404 |
| `test_answer_completed_session_returns_409` | Sesión ya completada → 409 |
| `test_status_returns_questions_answered` | GET /status → questions_answered correcto |
| `test_status_unknown_session_returns_404` | Session inexistente → 404 |
| `test_full_flow_integration` | Start + 4 answers → status completado |

---

## 7. Estructura del directorio `app/services/`

El directorio `app/services/` no existe en el worktree EPIC-004. Crear:

```
app/services/__init__.py   (vacío)
app/services/checkin_service.py
```

No crear `ceo_service.py` — pertenece a una epic posterior.

---

## 8. Decisiones de diseño importantes

### 8.1 Employee lookup en create_session

La pregunta 0 pide el nombre. No podemos crear el `Employee` real hasta obtener la respuesta. Opciones:

**A) Placeholder inmediato (sin migración):**
- `create_session` crea `Employee(name="__pending__")` y lo asocia a `CheckIn`.
- `process_answer(index=0)` actualiza `employee.name = answer_text.strip()`.
- Desventaja: si el proceso se abandona, queda un Employee con name "__pending__".

**B) FK nullable (con migración 010):**
- `create_session` crea `CheckIn(employee_id=None, ...)`.
- `process_answer(index=0)` hace `SELECT Employee WHERE name=answer LIMIT 1` o crea uno nuevo.
- Migración: `010_make_employee_id_nullable.py`.
- Ventaja: semánticamente correcto.
- Recomendado en esta spec.

**C) Employee lookup por nombre:**
- Al recibir el nombre, buscar `Employee` existente por nombre exacto (case-insensitive).
- Si existe, reusar; si no, crear nuevo.
- Ventaja: un empleado que hace check-in varios días acumula historia.
- Desventaja: nombres duplicados. Diferir a épicas futuras si el lookup por nombre es suficiente.

La **Opción B + C** combinada es la más robusta: FK nullable hasta saber el nombre, luego lookup o creación.

### 8.2 Interpolación de nombre en get_question

`QUESTIONS[1] = "¿En qué trabajaste hoy, {name}?"`. Si `name=""`, el resultado será `"¿En qué trabajaste hoy, ?"`. Alternativa: usar `name or "compañero"` en `get_question`:

```python
display_name = name if name else "compañero"
return QUESTIONS[index].format(name=display_name)
```

Esto hace la pregunta más natural. El implementador debe elegir.

### 8.3 answer_text sanitización

El `answer_text` del empleado en el índice 0 se usará como nombre. Aplicar `.strip()` mínimo. No normalizar a title-case automáticamente — respetar la forma en que el empleado escribe su nombre.

### 8.4 EmbeddingService task_type para check-in

Los chunks de check-in se usarán como documentos a indexar. Usar `task_type="RETRIEVAL_DOCUMENT"` en `complete_session`, consistente con cómo se indexan los `rag.chunks`.

---

## 9. Variables de entorno nuevas

No se requieren nuevas variables de entorno para EPIC-004. Todo utiliza `GEMINI_API_KEY` y `DATABASE_URL` ya presentes.

---

## 10. Secuencia de implementación recomendada

```
CHECKIN-01: app/core/checkin_flow.py
  → tests/test_core/test_checkin_flow.py (TDD: escribir primero)

CHECKIN-02: app/services/__init__.py
CHECKIN-02: app/services/checkin_service.py
  → tests/test_services/__init__.py
  → tests/test_services/test_checkin_service.py (TDD: escribir primero)
  → Si Opción B: alembic/versions/010_make_employee_id_nullable.py

CHECKIN-03/04/05: app/api/schemas/checkin_request.py
CHECKIN-03/04/05: app/api/schemas/checkin_response.py
CHECKIN-03/04/05: app/api/v1/checkin.py
  → app/dependencies.py (añadir get_checkin_service)
  → app/api/v1/router.py (registrar checkin_router)
  → tests/test_api/test_checkin.py (TDD: escribir primero)
```

CHECKIN-03, CHECKIN-04 y CHECKIN-05 comparten el mismo archivo `app/api/v1/checkin.py` y pueden implementarse en paralelo por funciones, pero el archivo se crea una sola vez.

---

## 11. Notas críticas para el implementador

1. **HerBase vs Base**: Los modelos `her.*` usan `HerBase` definido en `app/models/employee.py`, NO el `Base` de `app/models/base.py`. Importar `from app.models.employee import HerBase` si se necesita acceso a la metadata.

2. **alembic/env.py y dos metadatas**: El `env.py` actual usa `from app.models import Base` y `target_metadata = Base.metadata`. Esto significa que `alembic --autogenerate` NO detectará los modelos `her.*` automáticamente. Las migraciones 006-009 fueron escritas manualmente. La migración 010 (si se hace) también debe escribirse manualmente.

3. **Import de modelos en checkin_service.py**: Importar desde `app.models.checkin`, `app.models.checkin_chunk`, `app.models.employee` directamente (no desde `app.models` via __init__ para evitar posibles problemas de import order con las dos declarative bases).

4. **selectinload para chunks**: En `process_answer`, cargar `CheckIn.chunks` con `selectinload` para conocer el `current_index`. No usar `len(checkin.chunks)` sin haber cargado la relación explícitamente.

5. **Flush vs commit**: Dentro del service, usar `await db.flush()` para obtener IDs sin cerrar la transacción. El commit final debe hacerse desde el contexto del endpoint o del `get_db_session`.

6. **session_id**: Usar `str(uuid.uuid4())` — string, no UUID object. El modelo `CheckIn.session_id` es `String`, no `UUID`.

7. **El conftest.py de tests**: El fixture `db_session` hace rollback automático. Los tests de service deben usar `db_session` directamente. El `client` y `client_with_mock_embeddings` son para tests de endpoints.

8. **created_at en CheckIn**: El modelo `CheckIn` en EPIC-002 NO tiene `created_at` (warning W-1 del QA de EPIC-002). El QA marcó esto como deuda. Si se necesita en EPIC-004, añadir migración o usar `started_at` como equivalente.
