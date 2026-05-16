# EPIC-003: Servicio de Voz (STT / TTS)

**Status:** open
**Espera a:** EPIC-002

## Descripción
Integrar Google Cloud Speech-to-Text v2 para transcripción y Google Cloud Text-to-Speech para síntesis. Exponer ambos como endpoints HTTP que el frontend consume.

## Tareas
- SPEECH-01 — Crear `app/core/speech.py` (STT client, chirp_2, es-ES)
- SPEECH-02 — Crear `app/core/tts.py` (TTS client, Neural2, MP3)
- SPEECH-03 — Endpoint `POST /api/v1/speech/transcribe`
- SPEECH-04 — Endpoint `POST /api/v1/speech/synthesize`
- SPEECH-05 — Documentar credenciales (service account, roles GCP)

## Paralelización interna

| Tarea | Paralelo con | Espera a |
|-------|-------------|---------|
| SPEECH-01 | SPEECH-02, SPEECH-05 | — |
| SPEECH-02 | SPEECH-01, SPEECH-05 | — |
| SPEECH-03 | SPEECH-04 | SPEECH-01 |
| SPEECH-04 | SPEECH-03 | SPEECH-02 |
| SPEECH-05 | SPEECH-01, SPEECH-02 | — |
