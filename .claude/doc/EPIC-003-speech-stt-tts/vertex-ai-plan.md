# Vertex AI / Google Cloud Speech Plan — EPIC-003 (STT / TTS)

## Scope
This document is the authoritative implementation reference for EPIC-003.
It covers `app/core/speech.py`, `app/core/tts.py`, the two new HTTP endpoints,
settings additions, dependency wiring, and the full test strategy.
**Do not begin implementation until this file has been read in full.**

---

## 1. SDK Notes (google-cloud-speech v2 + google-cloud-texttospeech)

Both libraries are already pinned in `pyproject.toml`:
- `google-cloud-speech >= 2.28`
- `google-cloud-texttospeech >= 2.20`

### STT: Speech-to-Text v2
The v2 client (`google.cloud.speech_v2`) is **not** a drop-in replacement for v1.
Key differences the implementor must know:

```python
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import (
    RecognizeRequest,
    RecognitionConfig,
    AutoDetectDecodingConfig,
)
```

- The recognizer resource path must be fully qualified:
  `f"projects/{project}/locations/global/recognizers/_"`
  (`_` is the "default" inline recognizer — no pre-creation needed).
- `AutoDetectDecodingConfig` replaces `RecognitionConfig.encoding` + `sample_rate_hertz`
  and accepts webm/opus from the browser's `MediaRecorder` without extra parameters.
- The model field goes on `RecognitionConfig`, not on the request itself:
  `RecognitionConfig(model="chirp_2", language_codes=["es-ES"], auto_decoding_config=...)`
- The synchronous call is `client.recognize(request=RecognizeRequest(...))`.
  For async execution wrap it in `asyncio.to_thread(...)` — the v2 client has
  no native async support as of 2.28.
- `response.results[0].alternatives[0].transcript` and `.confidence` are the
  relevant output fields.

### TTS: Text-to-Speech
```python
from google.cloud.texttospeech import (
    TextToSpeechClient,
    SynthesisInput,
    VoiceSelectionParams,
    AudioConfig,
    AudioEncoding,
    SsmlVoiceGender,
)
```

- Synchronous client; wrap call in `asyncio.to_thread(...)` for async endpoints.
- `AudioEncoding.MP3` produces standard MPEG audio bytes.
- Voice name `es-ES-Neural2-A` is female. Make it configurable via settings.
- `response.audio_content` is `bytes` — return directly without base64 encoding.

### Authentication
Both clients pick up credentials automatically from the environment variable
`GOOGLE_APPLICATION_CREDENTIALS`. No explicit credential plumbing is required
in the service code. The service account at
`almawolf-7bbb108314b5.json` must have the roles:
- `roles/speech.client` (STT)
- `roles/cloudtexttospeech.user` (TTS)

---

## 2. Files to Create

### `app/core/speech.py`

```
STTService
  __init__(self, project: str, language_code: str = "es-ES") -> None
  async def transcribe(self, audio_bytes: bytes) -> dict
    # returns {"transcript": str, "confidence": float}
```

Implementation notes:
- Instantiate `SpeechClient()` inside `__init__` (credentials from env).
- Build `RecognitionConfig` once in `__init__` (immutable per service instance).
- `transcribe` runs `client.recognize(...)` inside `asyncio.to_thread`.
- If `response.results` is empty raise `STTError("No speech detected")`.
- Confidence defaults to `0.0` when the field is absent (chirp_2 does not
  always populate it).
- Catch `google.api_core.exceptions.GoogleAPICallError` → raise `STTError`.
- Never log `audio_bytes` contents; log only `len(audio_bytes)` and language.

### `app/core/tts.py`

```
TTSService
  __init__(self, language_code: str = "es-ES", voice_name: str = "es-ES-Neural2-A") -> None
  async def synthesize(self, text: str) -> bytes
    # returns raw MP3 bytes
```

Implementation notes:
- Instantiate `TextToSpeechClient()` inside `__init__`.
- `synthesize` runs `client.synthesize_speech(...)` inside `asyncio.to_thread`.
- Raise `TTSError("text must not be empty")` if `text.strip() == ""`.
- Cap text at 5000 characters (GCP TTS hard limit); raise `TTSError` if exceeded.
- Catch `google.api_core.exceptions.GoogleAPICallError` → raise `TTSError`.

### `app/api/v1/speech.py`

Two endpoints, one router:

```python
router = APIRouter(prefix="/speech", tags=["speech"])
```

**POST /speech/transcribe**
- Accepts `multipart/form-data` with field `audio: UploadFile`.
- Reads bytes, calls `stt_service.transcribe(audio_bytes)`.
- Returns `{"transcript": str, "confidence": float}` (200).
- 400 if no bytes received.
- 503 on `STTError`.

**POST /speech/synthesize**
- Accepts JSON `{"text": str}`.
- Calls `tts_service.synthesize(text)`.
- Returns `Response(content=audio_bytes, media_type="audio/mpeg")`.
- 400 if text empty or exceeds limit.
- 503 on `TTSError`.

Both endpoints use `Depends(get_stt_service)` / `Depends(get_tts_service)`
from `app/dependencies.py`.

---

## 3. Files to Edit

### `app/config.py`

Add the following fields to the `Settings` class after the existing Gemini block:

```python
# Google Cloud (Speech / TTS)
GOOGLE_CLOUD_PROJECT: str = ""
STT_LANGUAGE_CODE: str = "es-ES"
TTS_LANGUAGE_CODE: str = "es-ES"
TTS_VOICE_NAME: str = "es-ES-Neural2-A"
```

No validator is needed for `GOOGLE_CLOUD_PROJECT` — an empty string will cause
a descriptive `STTError` at runtime ("project must not be empty") rather than a
hard startup failure.

### `app/dependencies.py`

Add two factory functions:

```python
def get_stt_service(settings: Settings = Depends(get_settings)) -> "STTService":
    from app.core.speech import STTService
    return STTService(
        project=settings.GOOGLE_CLOUD_PROJECT,
        language_code=settings.STT_LANGUAGE_CODE,
    )

def get_tts_service(settings: Settings = Depends(get_settings)) -> "TTSService":
    from app.core.tts import TTSService
    return TTSService(
        language_code=settings.TTS_LANGUAGE_CODE,
        voice_name=settings.TTS_VOICE_NAME,
    )
```

### `app/api/v1/router.py`

```python
from app.api.v1.speech import router as speech_router
router.include_router(speech_router, tags=["speech"])
```

---

## 4. Test Files to Create

### `tests/test_core/test_speech.py`

Mock target: `google.cloud.speech_v2.SpeechClient`

Key test cases:
1. `test_transcribe_returns_transcript` — mock `recognize` returning a result with
   transcript `"hola mundo"` and confidence `0.95`.
2. `test_transcribe_empty_result_raises_stt_error` — mock returns `results=[]`.
3. `test_transcribe_api_error_raises_stt_error` — mock raises
   `google.api_core.exceptions.GoogleAPICallError("quota")`.
4. `test_transcribe_confidence_defaults_to_zero` — mock returns result with no
   confidence field set (or `0.0`).

Pattern: use `unittest.mock.patch` on `google.cloud.speech_v2.SpeechClient` at
the module level inside `app.core.speech`. Use `MagicMock` for the client
instance; wrap recognize response carefully — the v2 response objects are not
easily instantiatable, so construct them with `MagicMock` as well.

```python
# Minimal mock structure
mock_alternative = MagicMock()
mock_alternative.transcript = "hola mundo"
mock_alternative.confidence = 0.95
mock_result = MagicMock()
mock_result.alternatives = [mock_alternative]
mock_response = MagicMock()
mock_response.results = [mock_result]
mock_client.recognize.return_value = mock_response
```

### `tests/test_core/test_tts.py`

Mock target: `google.cloud.texttospeech.TextToSpeechClient`

Key test cases:
1. `test_synthesize_returns_bytes` — mock `synthesize_speech` returning
   `MagicMock(audio_content=b"fake-mp3")`.
2. `test_synthesize_empty_text_raises_tts_error`.
3. `test_synthesize_text_too_long_raises_tts_error` — pass 5001-character string.
4. `test_synthesize_api_error_raises_tts_error`.

### `tests/test_api/test_speech_endpoints.py`

Use the `client` fixture from `conftest.py` with dependency overrides for
`get_stt_service` and `get_tts_service`.

Key test cases:
1. `test_transcribe_200` — POST multipart with valid audio bytes → 200 + JSON.
2. `test_transcribe_empty_audio_400` — POST with 0-byte file → 400.
3. `test_transcribe_stt_error_503` — mock raises `STTError` → 503.
4. `test_synthesize_200` — POST JSON `{"text": "hola"}` → 200,
   `content-type: audio/mpeg`.
5. `test_synthesize_empty_text_400`.
6. `test_synthesize_tts_error_503` — mock raises `TTSError` → 503.

---

## 5. Schemas

No new Pydantic models needed for the response schemas. Use inline types:

```python
# transcribe response
class TranscriptResponse(BaseModel):
    transcript: str
    confidence: float

# synthesize request
class SynthesizeRequest(BaseModel):
    text: str
```

Place these in `app/api/schemas/speech.py` (new file).

---

## 6. Error Handling Contract

| Exception | HTTP status | User-facing detail |
|-----------|-------------|-------------------|
| `STTError("No speech detected")` | 503 | "Speech recognition service unavailable" |
| `STTError("project must not be empty")` | 503 | "Speech recognition service unavailable" |
| `TTSError("text must not be empty")` | 400 | "Text must not be empty" |
| `TTSError("text exceeds 5000 characters")` | 400 | "Text too long (max 5000 characters)" |
| `TTSError` (any other) | 503 | "Text-to-speech service unavailable" |

Raw GCP error messages must never surface to the frontend.

---

## 7. asyncio.to_thread Pattern

Both GCP clients are synchronous. The correct async wrapper:

```python
import asyncio

async def transcribe(self, audio_bytes: bytes) -> dict:
    def _sync_call() -> ...:
        return self._client.recognize(request=self._request_template(audio_bytes))
    response = await asyncio.to_thread(_sync_call)
    ...
```

Do **not** use `loop.run_in_executor(None, ...)` — `asyncio.to_thread` is
preferred in Python 3.10+.

---

## 8. Implementation Order (TDD)

1. Write failing tests in `tests/test_core/test_speech.py`.
2. Implement `app/core/speech.py` until tests pass.
3. Write failing tests in `tests/test_core/test_tts.py`.
4. Implement `app/core/tts.py` until tests pass.
5. Add settings fields to `app/config.py`.
6. Add dependency functions to `app/dependencies.py`.
7. Create `app/api/schemas/speech.py`.
8. Create `app/api/v1/speech.py`.
9. Register router in `app/api/v1/router.py`.
10. Write and pass `tests/test_api/test_speech_endpoints.py`.

---

## 9. Curl Acceptance Tests

```bash
# STT — transcribe a WAV/opus file
curl -s -X POST http://localhost:8000/api/v1/speech/transcribe \
  -F "audio=@sample_es.webm;type=audio/webm" | jq .
# Expected: {"transcript": "...", "confidence": ...}

# TTS — synthesize Spanish text
curl -s -X POST http://localhost:8000/api/v1/speech/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola, soy HER, tu asistente de check-in."}' \
  --output output.mp3
file output.mp3
# Expected: output.mp3: MPEG ADTS, layer III, v1
```
