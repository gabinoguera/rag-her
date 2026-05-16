# EPIC-005: Consulta del CEO (RAG)

**Status:** open
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
