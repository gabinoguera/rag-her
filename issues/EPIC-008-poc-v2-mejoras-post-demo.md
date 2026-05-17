# EPIC-008: HER PoC v2 — Mejoras post-demo

**Type:** feature
**Status:** open
**Fecha:** 2026-05-17

## Problem Statement
El PoC v1 está validado en producción. El primer día de uso reveló 4 áreas concretas de mejora: ciclo de vida de sesiones, retención de datos, calidad del RAG del CEO, y robustez de la infraestructura de voz.

## User Value
- **Empleados:** el sistema no acumula sesiones fantasma ni datos irrelevantes
- **CEO:** respuestas más precisas con contexto temporal y confianza más fiable
- **Operaciones:** escala a 80+ sesiones/día sin degradación ni intervención manual

## Issues hijas

| Issue | Título | Paralelo con | Espera a |
|-------|--------|-------------|---------|
| 008-01 | TTL y cierre automático de sesiones `in_progress` | 008-02, 008-03, 008-04 | — |
| 008-02 | Estrategia de retención y archivado (X días, sin borrado físico) | 008-01, 008-03, 008-04 | — |
| 008-03 | CEO: filtro temporal en query + mejora confidence (diversidad de empleados) | 008-01, 008-02, 008-04 | — |
| 008-04 | STT: chirp_2 configurable + fallback a `long` automático | 008-01, 008-02, 008-03 | — |
| 008-05 | Summarization before indexing (Gemini resume antes de embeddear) | — | 008-01 |
| 008-06 | Spike: Gemini Live API para conversación multimodal nativa | — | 008-01 a 008-05 |
| 008-07 | HER como entrevistadora conversacional (Gemini decide la siguiente pregunta) | — | 008-01 |

## Definition of Done
- 008-01 a 008-04 implementadas y en main
- ARCHITECTURE.md actualizado con estrategia de retención
- 008-05 con decisión documentada (implementar o descartar)
- 008-06 como spike técnico con conclusiones escritas

## Notes
- **008-01:** job periódico (cron o background task) que cierra sesiones con >4h sin actividad
- **008-02:** campo `archived_at` en `check_ins` + migración Alembic + config `DATA_RETENTION_DAYS`
- **008-03:** parámetro `days` en `/ceo/query` y `/ceo/summary` + confidence ponderada por nº de empleados distintos en sources
- **008-04:** `STT_MODEL=chirp_2` ya existe como config, falta detección automática de disponibilidad y fallback graceful
- **008-05:** campo `answer_summary` en `check_in_chunks`, guardar crudo + resumen, embeddear el resumen; evaluar impacto en calidad RAG
- **008-06:** investigación pura — Gemini Live API (preview), evaluar si elimina la necesidad de STT/TTS separados y cómo afecta al pipeline de embeddings
- **008-07:** reemplazar `checkin_flow.py` por un agente conversacional; Gemini recibe el historial completo y decide la siguiente pregunta o termina la sesión (máx. 6 turnos); el system prompt define a HER como entrevistadora que hace follow-up si la respuesta es vaga; el almacenamiento en pgvector no cambia
