# EPIC-007: Limpieza del Repositorio Legacy

**Status:** open
**Espera a:** EPIC-001 (puede ejecutarse en paralelo con Epics 3, 4, 5, 6)

## Descripción
Eliminar todo el código de generación de presupuestos. Dejar el repositorio limpio y coherente con el dominio HER.

## Tareas
- CLEAN-01 — Borrar módulos core legacy (`chunking`, `ranking`, `quote_generation_pipeline`, etc.)
- CLEAN-02 — Borrar modelos legacy (`document`, `ingestion_log`, `search_log`, `chunk`)
- CLEAN-03 — Borrar datos de ejemplo (`estimation_samples/`, `transcriptions/`)
- CLEAN-04 — Actualizar `app/api/v1/router.py` (dejar health, checkin, ceo, speech)
- CLEAN-05 — Actualizar `app/main.py` (título HER, montar `adapters/primary/web/`)
- CLEAN-06 — Actualizar `README.md`

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| CLEAN-01 | CLEAN-02, CLEAN-03 | — |
| CLEAN-02 | CLEAN-01, CLEAN-03 | — |
| CLEAN-03 | CLEAN-01, CLEAN-02 | — |
| CLEAN-04 | CLEAN-05 | CLEAN-01 |
| CLEAN-05 | CLEAN-06 | CLEAN-04 |
| CLEAN-06 | CLEAN-05 | CLEAN-04 |
