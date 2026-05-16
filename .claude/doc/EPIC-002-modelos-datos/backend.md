# Backend Implementation Plan — EPIC-002: Modelos de Datos y Migraciones

**Fecha:** 2026-05-16
**Agente:** @backend-developer
**Estado:** draft

---

## 1. Contexto y restricciones clave

### Base.metadata y schema "rag"

`app/models/base.py` define `Base` con `MetaData(schema="rag")`. Este archivo NO debe modificarse. Todos los modelos nuevos deben declarar `__table_args__` con `{"schema": "her"}` explícitamente para sobrescribir el schema default del metadata.

Cuando `__table_args__` también necesita contener constraints o índices (como en `CheckInChunk`), se usa la forma tupla con el dict como último elemento:

```python
__table_args__ = (
    CheckConstraint(...),
    Index(...),
    {"schema": "her"},
)
```

Cuando no hay constraints adicionales, se usa la forma dict directa:

```python
__table_args__ = {"schema": "her"}
```

### TimestampMixin

`TimestampMixin` ya provee:
- `id: Mapped[uuid.UUID]` — UUID PK con `server_default=text("uuid_generate_v4()")`
- `created_at: Mapped[datetime]` — TIMESTAMP WITH TIME ZONE con `server_default=text("now()")`

No crear un mixin alternativo. Usarlo tal cual para los 3 modelos nuevos.

### pgvector

El patrón existente en `app/models/chunk.py` usa `from pgvector.sqlalchemy import Vector`. Los nuevos modelos de HER usan dimensión 768 (Gemini `text-multilingual-embedding-002`) en lugar de 1536.

### Alembic env.py

`alembic/env.py` ya tiene `version_table_schema = os.environ.get("DATABASE_SCHEMA", "her")`. Esto significa que la tabla `alembic_version` se almacena en el schema `her`, que aún no existe en la base de datos. Por eso la migración 006 debe crear el schema `her` ANTES de que Alembic intente escribir en él.

**Implicación crítica:** La migración 006 debe ejecutarse ANTES de cualquier otra migración de esta epic, o el `alembic upgrade head` fallará porque `her.alembic_version` no puede escribirse en un schema inexistente.

---

## 2. Archivos a crear

### 2.1 `app/models/employee.py`

```python
import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = {"schema": "her"}

    name: Mapped[str] = mapped_column(Text, nullable=False)
```

**Notas:**
- No hay relaciones definidas aquí porque `CheckIn` tiene la FK hacia `Employee`. SQLAlchemy permite relaciones unidireccionales; la relación `back_populates` puede añadirse en EPIC-003 cuando el servicio de check-in la requiera.
- `name` usa `Text` (no `VARCHAR`) para evitar límites arbitrarios. Revisión: si hay requisito de longitud máxima, usar `VARCHAR(255)`.

### 2.2 `app/models/checkin.py`

```python
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CheckIn(TimestampMixin, Base):
    __tablename__ = "check_ins"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("her.employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="in_progress")
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_check_ins_status",
        ),
        Index("idx_check_ins_session_id", "session_id"),
        Index("idx_check_ins_employee_id", "employee_id"),
        {"schema": "her"},
    )
```

**Notas:**
- `session_id` tiene `unique=True` a nivel de columna Y un índice explícito `idx_check_ins_session_id`. SQLAlchemy crea un índice implícito para `unique=True`, pero el índice explícito garantiza un nombre predecible para dropear en downgrade.
- La FK usa `"her.employees.id"` como string (forma `schema.table.column`) porque los dos modelos pertenecen a schemas distintos del `Base.metadata` default (`rag`). Esta forma string evita problemas de resolución de metadata cross-schema.
- `status` tiene `server_default="in_progress"` para que inserciones sin status explícito sean válidas a nivel de DB.

### 2.3 `app/models/checkin_chunk.py`

```python
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CheckInChunk(TimestampMixin, Base):
    __tablename__ = "check_in_chunks"

    checkin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("her.check_ins.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "question_index BETWEEN 0 AND 3",
            name="ck_check_in_chunks_question_index",
        ),
        Index("idx_check_in_chunks_checkin_id", "checkin_id"),
        {"schema": "her"},
    )
```

**Notas:**
- El índice HNSW sobre `embedding` NO se define en `__table_args__` porque SQLAlchemy no tiene soporte nativo para `USING hnsw ... WITH (m=16, ef_construction=200)`. Este índice se crea directamente con `op.execute()` en la migración 009.
- `Mapped[list[float] | None]` es el tipo correcto para pgvector en SQLAlchemy con Pydantic v2. `nullable=True` porque los embeddings se generan asíncronamente después del check-in.

---

## 3. Archivos a editar

### 3.1 `app/models/__init__.py`

Añadir imports de los tres modelos nuevos:

```python
from app.models.base import Base, TimestampMixin
from app.models.chunk import Chunk
from app.models.employee import Employee
from app.models.checkin import CheckIn
from app.models.checkin_chunk import CheckInChunk

__all__ = ["Base", "TimestampMixin", "Chunk", "Employee", "CheckIn", "CheckInChunk"]
```

**Importante:** El orden de imports importa para que SQLAlchemy resuelva FKs correctamente en el metadata. `Employee` debe importarse antes que `CheckIn`, y `CheckIn` antes que `CheckInChunk`.

### 3.2 `tests/conftest.py`

El cleanup de tablas en `conftest.py` actualmente puede referenciar tablas del schema `rag` (search_logs, ingestion_logs) que ya fueron eliminadas en EPIC-001. Verificar y limpiar. No añadir cleanup de tablas `her.*` en esta epic — eso pertenece a los tests de EPIC-003.

---

## 4. Migraciones Alembic (006-009)

### Convenciones de naming observadas en el proyecto

- Archivo: `NNN_descripcion_corta.py`
- `revision: str = "NNN"` (string, no int)
- `down_revision: str | None = "NNN-1"`
- `op.create_table(name, *columns, schema="her")` para tablas con schema explícito
- `op.execute(raw_sql)` para DDL no soportado por Alembic (HNSW, DROP INDEX con schema)
- Imports: `import sqlalchemy as sa`, `from sqlalchemy.dialects import postgresql`, `from alembic import op`

### 4.1 Migración 006: `alembic/versions/006_create_her_schema.py`

```python
"""Create her schema.

Revision ID: 006
Revises: 005
Create Date: 2026-05-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS her")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS her CASCADE")
```

**Notas:**
- NO se crea `CREATE EXTENSION IF NOT EXISTS vector` — ya existe desde migración 001. Crearla de nuevo no falla (es idempotente con IF NOT EXISTS), pero es innecesario y confuso.
- `DROP SCHEMA ... CASCADE` en downgrade eliminará todas las tablas del schema `her` incluyendo las creadas por 007, 008 y 009. Esto es correcto: si se hace downgrade a 005, el schema completo desaparece.
- `IF NOT EXISTS` en upgrade garantiza idempotencia — si el schema ya existe (entorno de desarrollo donde se ejecutó manualmente), no falla.

### 4.2 Migración 007: `alembic/versions/007_create_employees.py`

```python
"""Create her.employees table.

Revision ID: 007
Revises: 006
Create Date: 2026-05-16 00:00:01.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="her",
    )


def downgrade() -> None:
    op.drop_table("employees", schema="her")
```

### 4.3 Migración 008: `alembic/versions/008_create_checkins.py`

```python
"""Create her.check_ins table.

Revision ID: 008
Revises: 007
Create Date: 2026-05-16 00:00:02.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_ins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "session_id",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default="in_progress",
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_check_ins_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["her.employees.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_check_ins_session_id"),
        schema="her",
    )

    op.create_index(
        "idx_check_ins_session_id",
        "check_ins",
        ["session_id"],
        schema="her",
    )
    op.create_index(
        "idx_check_ins_employee_id",
        "check_ins",
        ["employee_id"],
        schema="her",
    )


def downgrade() -> None:
    op.drop_index("idx_check_ins_employee_id", table_name="check_ins", schema="her")
    op.drop_index("idx_check_ins_session_id", table_name="check_ins", schema="her")
    op.drop_table("check_ins", schema="her")
```

**Notas:**
- La FK referencia `"her.employees.id"` como string en la lista de `ForeignKeyConstraint`. Alembic necesita el schema calificado completo porque la tabla referenciada no está en el schema default del metadata (`rag`).
- Se añade `UniqueConstraint` explícito con nombre predecible (`uq_check_ins_session_id`) además del índice, para que la constraint sea nombrada y se pueda dropear limpiamente en downgrade si se necesita.

### 4.4 Migración 009: `alembic/versions/009_create_checkin_chunks.py`

```python
"""Create her.check_in_chunks table with HNSW index.

Revision ID: 009
Revises: 008
Create Date: 2026-05-16 00:00:03.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_in_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("checkin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.CheckConstraint(
            "question_index BETWEEN 0 AND 3",
            name="ck_check_in_chunks_question_index",
        ),
        sa.ForeignKeyConstraint(
            ["checkin_id"],
            ["her.check_ins.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="her",
    )

    op.create_index(
        "idx_check_in_chunks_checkin_id",
        "check_in_chunks",
        ["checkin_id"],
        schema="her",
    )

    # HNSW index for vector similarity search (cosine distance, 768 dims)
    # m=16: number of connections per layer (higher = better recall, more memory)
    # ef_construction=200: size of dynamic candidate list during construction (higher = better recall, slower build)
    op.execute(
        "CREATE INDEX idx_check_in_chunks_embedding "
        "ON her.check_in_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS her.idx_check_in_chunks_embedding")
    op.drop_index(
        "idx_check_in_chunks_checkin_id",
        table_name="check_in_chunks",
        schema="her",
    )
    op.drop_table("check_in_chunks", schema="her")
```

**Notas críticas sobre el índice HNSW:**
- `op.execute()` con SQL raw es el único método soportado para HNSW en Alembic (no hay wrapper de alto nivel).
- El índice se crea DESPUÉS del `op.create_table()` porque PostgreSQL necesita que la tabla exista primero.
- En downgrade, `DROP INDEX IF EXISTS her.idx_check_in_chunks_embedding` usa la forma `schema.index_name`. PostgreSQL almacena los índices en el schema de la tabla, por eso se necesita el prefijo `her.`.
- Parámetros HNSW idénticos a los de `rag.chunks` (m=16, ef_construction=200) para consistencia.

---

## 5. Orden de ejecución de migraciones

```
005 (search_logs) → 006 (her schema) → 007 (employees) → 008 (check_ins) → 009 (check_in_chunks)
```

La cadena de `down_revision` es lineal: 006→005, 007→006, 008→007, 009→008.

**Problema potencial con version_table_schema:** `alembic/env.py` configura `version_table_schema="her"`. Si la base de datos está en migración 005 y el schema `her` no existe aún, Alembic intentará hacer un SELECT en `her.alembic_version` antes de ejecutar la migración 006 — lo que falla.

**Solución:** Verificar que el primer `alembic upgrade head` en una base de datos limpia funcione. Si falla, hay dos opciones:
1. Mover la creación del schema `her` a la migración 001 (riesgoso — modifica migración ya aplicada en producción).
2. Crear el schema `her` manualmente antes del primer `alembic upgrade` en entornos donde 006 no se haya corrido.

En la práctica, si las migraciones 001-005 ya están aplicadas en la base de datos de producción/staging, entonces el schema `her` no existe y `alembic upgrade 006` fallará al intentar registrar la migración en `her.alembic_version`.

**Recomendación:** Ejecutar el siguiente SQL manualmente en la DB antes del primer `alembic upgrade` post-EPIC-002 deployment:
```sql
CREATE SCHEMA IF NOT EXISTS her;
```
Luego `alembic upgrade head` aplicará 006-009 normalmente. La migración 006 tiene `IF NOT EXISTS` por lo que no falla si el schema ya existe.

Alternativamente, revisar si `env.py` puede hacer fallback al schema `public` para `version_table_schema` cuando el schema `her` no existe aún (más complejo, fuera de scope de esta epic).

---

## 6. Fases de implementación con TDD

| # | Phase | Description | Status | Parallel | Depends | TDD |
|---|-------|-------------|--------|----------|---------|-----|
| 1 | DB-01 | Crear `app/models/employee.py` | pending | DB-02, DB-03 | — | yes |
| 2 | DB-02 | Crear `app/models/checkin.py` | pending | DB-01, DB-03 | — | yes |
| 3 | DB-03 | Crear `app/models/checkin_chunk.py` con Vector(768) | pending | DB-01, DB-02 | — | yes |
| 4 | DB-04 | Migración `006_create_her_schema.py` | pending | — | — | yes |
| 5 | DB-05 | Migración `007_create_employees.py` | pending | DB-06 | DB-01, DB-04 | yes |
| 6 | DB-06 | Migración `008_create_checkins.py` | pending | DB-05 | DB-02, DB-04 | yes |
| 7 | DB-07 | Migración `009_create_checkin_chunks.py` + HNSW | pending | — | DB-03, DB-06 | yes |
| 8 | DB-08 | Actualizar `app/models/__init__.py` | pending | — | DB-01, DB-02, DB-03 | yes |
| 9 | DB-09 | Verificar ciclo completo `alembic upgrade head` + `downgrade base` | pending | — | DB-07, DB-08 | yes |

**Estrategia TDD para modelos (DB-01 a DB-03):**
- Test red: importar `Employee`/`CheckIn`/`CheckInChunk` desde `app.models` — falla con `ImportError`.
- Test green: crear el archivo del modelo con las columnas correctas — test pasa.
- Test refactor: verificar que `Employee.__table__.schema == "her"`, que `CheckInChunk.__table__.c.embedding.type` es `Vector(768)`, que el CHECK constraint de `status` tiene el nombre esperado.

**Estrategia TDD para migraciones (DB-04 a DB-07):**
- Test red: `alembic upgrade 009` — falla porque los archivos no existen.
- Test green: crear los 4 archivos de migración — `alembic upgrade head` pasa.
- Test refactor: `alembic downgrade base` — todas las tablas desaparecen limpiamente; `alembic upgrade head` de nuevo — tablas recreadas sin errores.

---

## 7. Variables de entorno

No se añaden variables nuevas. Las relevantes ya existentes:

| Variable | Valor esperado | Descripción |
|----------|---------------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | URL de conexión PostgreSQL |
| `DATABASE_SCHEMA` | `her` | Schema para `alembic_version` (ya configurado en env.py) |

---

## 8. Consideraciones adicionales

### Cross-schema FKs en SQLAlchemy

Cuando dos modelos están en schemas distintos y usan el mismo `Base` (cuyo metadata tiene `schema="rag"`), las FKs deben especificarse como strings calificados con schema: `ForeignKey("her.employees.id")`. Si se usa la referencia de clase directa (`ForeignKey(Employee.id)`), SQLAlchemy puede resolver incorrectamente el schema.

### Chunk.py legacy (schema rag)

`app/models/chunk.py` tiene `Vector(1536)`. La nota de EPIC-001 dice que `chunk.py` no fue eliminado en RAG-05. Esta epic no modifica `chunk.py` — eso está fuera de scope. Los tests de EPIC-001 que están con `@pytest.mark.skip(reason="Pendiente EPIC-002")` deben ser re-evaluados: si los tests se saltaban por `Vector(1536)` vs `Vector(768)`, siguen sin resolverse con esta epic porque `rag.chunks` sigue en 1536d. Solo los tests que dependían de que `her.check_in_chunks` existiera pueden reactivarse.

### Relaciones SQLAlchemy (diferido a EPIC-003)

Los modelos en esta epic no definen `relationship()`. Las relaciones bidireccionales (`Employee.check_ins`, `CheckIn.chunks`) se añadirán en EPIC-003 cuando los servicios de check-in las requieran. Esto evita circular imports y mantiene los modelos simples en esta fase.
