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
