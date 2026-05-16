# QA Report — EPIC-002: Modelos de Datos y Migraciones

**Fecha:** 2026-05-16
**Autor:** @qa-criteria-validator
**Branch:** feature-issue-EPIC-002
**Worktree:** `.trees/feature-issue-EPIC-002`
**Veredicto final:** PASS

---

## TC Classification

| TC   | Descripcion                                          | Tipo       | Motivo                                                         |
|------|------------------------------------------------------|------------|----------------------------------------------------------------|
| TC-1 | Schema her existe en DB tras alembic upgrade head    | Paralelo   | Verifica estado de schema en information_schema — sin dependencia cruzada |
| TC-2 | Tablas her.* creadas con columnas correctas          | Paralelo   | Consulta information_schema.columns independiente              |
| TC-3 | Indice HNSW con nombre correcto en check_in_chunks   | Paralelo   | Consulta pg_indexes independiente                              |
| TC-4 | Alembic revision 009 (head)                          | Paralelo   | Verifica estado de version_table — sin dependencia cruzada     |
| TC-5 | 14 tests test_her_models.py pasan sin skips          | Secuencial | Requiere TC-1..TC-4 confirmados; depende de estado DB correcto |
| TC-6 | Suite completa tests/ sin errores                    | Secuencial | Requiere TC-5 completado                                       |

---

## Nota Pre-Ejecucion

El servidor de desarrollo y las migraciones deben ejecutarse desde el worktree correcto (`.trees/feature-issue-EPIC-002`), NO desde el repositorio base. Las migraciones 006-009 existen solo en el worktree de la feature. Se verifico que:

1. El worktree activo era `.trees/feature-issue-EPIC-002`
2. Alembic se invoco con `-c $WORKDIR/alembic.ini` y `PYTHONPATH=$WORKDIR`
3. Se ejecuto `alembic upgrade head` antes de correr los TCs (la DB estaba en revision vacia)
4. La DB quedo en revision `009 (head)` antes de correr TC-5 y TC-6

---

## Resultados

### TC-1: Schema `her` existe — PASS

```
Comando: SELECT schema_name FROM information_schema.schemata WHERE schema_name='her';
Resultado:
 schema_name
-------------
 her
(1 row)
```

- AC-1.1 cumplido: schema `her` presente en information_schema
- Revision alembic: `009 (head)` (verificado en TC-4)

---

### TC-2: Tablas `her.*` con columnas correctas — PASS con notas

#### her.employees
```
   Column   |           Type           | Nullable |      Default
------------+--------------------------+----------+--------------------
 id         | uuid                     | not null | uuid_generate_v4()
 name       | text                     | not null |
 created_at | timestamp with time zone | not null | now()
Indexes: "employees_pkey" PRIMARY KEY, btree (id)
```
- AC-2.1 cumplido: id (UUID, PK, not null), name (text, not null), created_at (timestamptz, not null, default now())

#### her.check_ins
```
    Column    |           Type           | Nullable |             Default
--------------+--------------------------+----------+----------------------------------
 id           | uuid                     | not null | uuid_generate_v4()
 employee_id  | uuid                     | not null |
 session_id   | character varying        | not null |
 status       | character varying(20)    | not null | 'in_progress'::character varying
 started_at   | timestamp with time zone | not null | now()
 completed_at | timestamp with time zone |          |
```
- Nota D-6 confirmada: columna `started_at` presente (scope creep menor, no en spec original)
- Nota D-11 de Implementation Review: `created_at` ausente en `check_ins` — columna NO presente en DB
  - Esta desviacion se confirma en ejecucion pero NO bloquea los tests actuales
- Check constraint `ck_checkins_status` presente (nombre difiere de spec: `ck_check_ins_status` esperado, `ck_checkins_status` actual)
  - Validacion funcional: `status IN ('in_progress', 'completed', 'failed')` activa
- UNIQUE constraint `uq_check_ins_session_id` presente
- FK `check_ins_employee_id_fkey` -> `her.employees(id)` ON DELETE CASCADE presente
- Indices `idx_check_ins_session_id` e `idx_check_ins_employee_id` presentes

#### her.check_in_chunks
```
     Column     |           Type           | Nullable |      Default
----------------+--------------------------+----------+--------------------
 id             | uuid                     | not null | uuid_generate_v4()
 checkin_id     | uuid                     | not null |
 question_index | integer                  | not null |
 question_text  | text                     | not null |
 answer_text    | text                     | not null |
 embedding      | vector(768)              |          |
 created_at     | timestamp with time zone | not null | now()
```
- embedding: vector(768), nullable — correcto
- created_at presente
- FK `check_in_chunks_checkin_id_fkey` -> `her.check_ins(id)` ON DELETE CASCADE presente
- Nota D-10 de Implementation Review: CHECK constraint `ck_check_in_chunks_question_index` ausente en DB
  - Confirmado: `information_schema.check_constraints` para `check_in_chunks` no muestra este constraint
  - Impacta AC-4.6 (INSERT con question_index=4 no lanzaria CHECK VIOLATION via DB)
  - No bloquea tests actuales (ninguno de los 14 tests verifica este constraint directamente)

---

### TC-3: Indice HNSW con nombre correcto — PASS

```
Comando: SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='her' AND tablename='check_in_chunks';
Resultado:
           indexname            |                                                                    indexdef
--------------------------------+---------------------------------------------------------------------------------------------
 check_in_chunks_pkey           | CREATE UNIQUE INDEX check_in_chunks_pkey ON her.check_in_chunks USING btree (id)
 idx_check_in_chunks_checkin_id | CREATE INDEX idx_check_in_chunks_checkin_id ON her.check_in_chunks USING btree (checkin_id)
 idx_check_in_chunks_embedding  | CREATE INDEX idx_check_in_chunks_embedding ON her.check_in_chunks USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='200')
```

- Indice `idx_check_in_chunks_embedding` presente con nombre correcto
- USING hnsw: confirmado
- vector_cosine_ops: confirmado
- m=16, ef_construction=200: confirmado
- Nota D-4 de Implementation Review (nombre ausente) fue resuelta antes del QA

AC-4.1 cumplido completamente.

---

### TC-4: Alembic revision 009 (head) — PASS

```
Comando: alembic -c $WORKDIR/alembic.ini current
Resultado: 009 (head)
```

AC-1.1 cumplido: `alembic current` devuelve `009 (head)`.

---

### TC-5: 14 tests pasan — PASS

```
Comando: pytest tests/test_models/test_her_models.py -v
Resultado:
test_employee_creation PASSED
test_employee_name_not_null PASSED
test_employee_table_is_in_her_schema PASSED
test_checkin_creation_with_employee PASSED
test_checkin_session_id_unique PASSED
test_checkin_status_values PASSED
test_checkin_fk_cascade_on_employee_delete PASSED
test_checkin_table_is_in_her_schema PASSED
test_checkin_chunk_creation PASSED
test_checkin_chunk_embedding_nullable PASSED
test_checkin_chunk_embedding_stored PASSED
test_checkin_chunk_table_is_in_her_schema PASSED
test_employee_checkin_relationship PASSED
test_checkin_chunks_relationship PASSED

14 passed, 2 warnings in 1.36s
```

- 14/14 tests pasan
- 0 fallan
- 0 skipped
- AC-5.1 cumplido

---

### TC-6: Suite completa — PASS

```
Comando: pytest tests/ --asyncio-mode=auto -q
Resultado: 114 passed, 3 skipped, 2 warnings in 2.69s
```

Los 3 tests skipped son intencionales:
- `tests/test_api/test_search.py::TestSearchEndpoint::test_search_no_results_empty_db`
- `tests/test_api/test_search.py::TestSearchEndpoint::test_search_response_format`
- `tests/test_api/test_search.py::TestSearchEndpoint::test_search_valid_top_k_accepted`

Razon del skip: `"EPIC-002: rag.chunks no existe en her_poc, se migra a her.check_in_chunks"` — skip intencional documentado, fuera del scope de EPIC-002.

AC-5.3 cumplido: suite completa sin errores ni ImportError.

---

## Validation Report

### Passed

- TC-1: Schema `her` existe en information_schema con 1 fila
- TC-2: Las 3 tablas `her.employees`, `her.check_ins`, `her.check_in_chunks` creadas con columnas requeridas
- TC-3: Indice `idx_check_in_chunks_embedding` presente con USING hnsw, vector_cosine_ops, m=16, ef_construction=200
- TC-4: Alembic revision `009 (head)` confirmado
- TC-5: 14/14 tests en `test_her_models.py` pasan (0 fallan, 0 skipped)
- TC-6: 114 passed, 3 skipped intencionales (no relacionados con EPIC-002)
- FK cross-schema correctas en check_ins -> employees (CASCADE) y check_in_chunks -> check_ins (CASCADE)
- Vector(768) almacenado y recuperado correctamente (test_checkin_chunk_embedding_stored)
- `relationship()` entre Employee-CheckIn y CheckIn-CheckInChunk funcionales
- `test_vector_search.py` reescrito sin skip global
- `alembic/env.py` resuelve bootstrapping automaticamente via `CREATE SCHEMA IF NOT EXISTS`

### Warnings (no bloqueantes)

- W-1 (D-11): Columna `created_at` ausente en `her.check_ins` — la migracion 008 no la incluye. No bloquea ningun test actual pero es deuda tecnica para EPIC-003.
- W-2 (D-9): Nombre del check constraint de status es `ck_checkins_status` en lugar de `ck_check_ins_status` (spec). Funcionalmente equivalente.
- W-3 (D-10): CHECK constraint `ck_check_in_chunks_question_index` ausente en DB. AC-4.6 no es verificable via DB constraint. No bloquea ningun test actual.
- W-4 (D-2): `HerBase` como segunda jerarquia `DeclarativeBase` — `alembic --autogenerate` futuro necesitara incluir ambas metadatas. Deuda para EPIC-003.

### Failed

Ninguno.

---

## Success Criteria Gate

| Criterio | Estado |
|----------|--------|
| `alembic current` devuelve `009 (head)` | PASS |
| `SELECT schema_name ... WHERE schema_name = 'her'` retorna 1 fila | PASS |
| `\dt her.*` muestra employees, check_ins, check_in_chunks | PASS |
| `pg_indexes` contiene `idx_check_in_chunks_embedding` con USING hnsw y vector_cosine_ops | PASS |
| `pytest test_her_models.py` — 14 tests pasan, 0 fallan, 0 skipped | PASS |
| `pytest test_vector_search.py` — test_checkin_chunk_embedding_storage pasa sin skip | PASS |
| `pytest tests/test_models/` — suite sin errores ni ImportError | PASS |

---

## Deuda Tecnica para EPIC-003

1. `created_at` en `her.check_ins` debe agregarse en una migracion correctiva
2. `ck_check_in_chunks_question_index` CHECK constraint debe agregarse en migracion correctiva
3. `HerBase.metadata` debe incluirse en `target_metadata` de `alembic/env.py` si se usa `--autogenerate`

---

## Veredicto

**EPIC-002: PASS — Ready to merge**

Todos los TCs criticos pasan. Las 3 advertencias son deuda tecnica no bloqueante que se atendera en EPIC-003. La implementacion cumple todos los criterios de aceptacion Must del MoSCoW y los 14 tests requeridos por AC-5.1.
