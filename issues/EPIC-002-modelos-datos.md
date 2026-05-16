# EPIC-002: Modelos de Datos y Migraciones

**Status:** open
**Espera a:** EPIC-001

## Descripción
Definir el nuevo modelo de datos para HER. Tres tablas: empleados, sesiones de check-in y chunks vectorizados. Índice HNSW sobre vectores de 768 dimensiones (Gemini).

## Tareas
- DB-01 — Crear modelo `app/models/employee.py`
- DB-02 — Crear modelo `app/models/checkin.py`
- DB-03 — Crear modelo `app/models/checkin_chunk.py` con Vector(768)
- DB-04 — Migración `006_create_her_schema.py`
- DB-05 — Migración `007_create_employees.py`
- DB-06 — Migración `008_create_checkins.py`
- DB-07 — Migración `009_create_checkin_chunks.py` + índice HNSW
- DB-08 — Verificar ciclo completo de migraciones

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| DB-01 | DB-02, DB-03 | — |
| DB-02 | DB-01, DB-03 | — |
| DB-03 | DB-01, DB-02 | — |
| DB-04 | — | — |
| DB-05 | DB-06 | DB-01, DB-04 |
| DB-06 | DB-05 | DB-02, DB-04 |
| DB-07 | — | DB-03, DB-06 |
| DB-08 | — | DB-07 |
