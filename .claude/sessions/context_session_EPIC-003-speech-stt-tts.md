# Context Session: EPIC-003 Speech STT/TTS

## Estado
- Issue: `/issues/EPIC-003-speech-stt-tts.md` — Technical Spec añadida (secciones 1-8)
- Plan detallado: `.claude/doc/EPIC-003-speech-stt-tts/vertex-ai-plan.md`
- Status: IMPLEMENTACION COMPLETA — 139 passed, 3 skipped, 0 failures
- Worktree: `.trees/feature-issue-EPIC-003/`

## Stack existente relevante
- FastAPI en `app/main.py`, routers en `app/api/v1/router.py`
- Pattern de servicios: clases en `app/core/`, inyectadas via `app/dependencies.py`
- Configuración centralizada en `app/config.py` (pydantic-settings, `.env`)
- Tests con pytest-asyncio, httpx AsyncClient, mocks via `unittest.mock`
- Auth GCP: `GOOGLE_APPLICATION_CREDENTIALS` apunta a service account JSON
- `google-cloud-speech>=2.28` y `google-cloud-texttospeech>=2.20` ya en pyproject.toml

## Ficheros creados (EPIC-003)
- `app/core/speech.py` — STTService (SpeechClient v2, chirp_2, asyncio.to_thread)
- `app/core/tts.py` — TTSService (TextToSpeechClient, Neural2-A, MP3, asyncio.to_thread)
- `app/api/v1/speech.py` — router con endpoints /transcribe y /synthesize
- `app/api/schemas/speech.py` — TranscribeResponse, SynthesizeRequest Pydantic models
- `tests/test_core/test_speech.py` — 8 tests STT (todos verdes)
- `tests/test_core/test_tts.py` — 8 tests TTS (todos verdes)
- `tests/test_api/test_speech_endpoints.py` — 9 tests endpoints (todos verdes)

## Ficheros editados
- `app/config.py` — añadidos GOOGLE_CLOUD_PROJECT, STT_LANGUAGE_CODE, TTS_LANGUAGE_CODE, TTS_VOICE_NAME
- `app/dependencies.py` — añadidos get_stt_service, get_tts_service
- `app/api/v1/router.py` — registrado speech_router

## Notas de implementación importantes
- SynthesizeRequest no tiene validadores Pydantic para texto vacío/largo: la validación
  la hace el endpoint directamente con HTTPException(400) — los validadores Pydantic
  devolverían 422 en vez de 400 como exige la spec
- STTError y TTSError son clases de excepción propias en cada módulo (no exponen
  mensajes raw de GCP al frontend)
- Los endpoints devuelven 503 cuando hay errores GCP, 400 para validación local
- TTSService.synthesize: texttospeech.AudioEncoding.MP3 (no AudioEncoding.MP3 directo)
- El fixture `client` del conftest.py de tests no override las dependencias de speech
  — los tests de endpoints manejan sus propios overrides localmente

## QA Report
- Path: `.claude/doc/EPIC-003-speech-stt-tts/qa-report.md`
- Fecha: 2026-05-16
- Veredicto: PASSED — Ready to merge
- TCs ejecutados: 4 (todos paralelos)
- Resultado: TC-1 (16/16), TC-2 (9/9), TC-3 (124 passed / 0 regresiones EPIC-003), TC-4 (settings OK)
- 8/8 acceptance criteria cubiertos
- 7/7 Must Have cumplidos
- Warning no bloqueante: 15 failures pre-existentes por contaminacion de transacciones DB en suite completa
