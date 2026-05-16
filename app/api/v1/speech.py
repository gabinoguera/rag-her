"""Speech endpoints for EPIC-003.

Provides:
  POST /api/v1/speech/transcribe  — audio file → transcript JSON
  POST /api/v1/speech/synthesize  — text JSON → MP3 audio bytes
"""

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.schemas.speech import SynthesizeRequest, TranscribeResponse
from app.core.speech import STTError, STTService
from app.core.tts import TTSError, TTSService
from app.dependencies import get_stt_service, get_tts_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/speech")


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio to text",
    description=(
        "Upload a raw audio file (webm/opus, wav, mp3, …) and receive the "
        "recognised text with a confidence score.  Uses Google Cloud "
        "Speech-to-Text v2 (chirp_2 model, es-ES by default)."
    ),
)
async def transcribe(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    stt: STTService = Depends(get_stt_service),
) -> TranscribeResponse:
    """Transcribe the uploaded audio file.

    Returns 400 if the file is empty, 503 if the STT service is unavailable.
    """
    data = await audio.read()

    if not data:
        raise HTTPException(status_code=400, detail="audio file is empty")

    try:
        result = await stt.transcribe(data)
    except STTError as exc:
        logger.warning("STT transcription failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Speech recognition unavailable") from exc

    return TranscribeResponse(
        transcript=result["transcript"],
        confidence=result["confidence"],
    )


@router.post(
    "/synthesize",
    summary="Synthesise text to MP3 audio",
    description=(
        "Send plain text and receive an MP3 audio stream synthesised by "
        "Google Cloud Text-to-Speech (Neural2-A, es-ES by default).  "
        "Maximum text length is 5 000 characters."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "MP3 audio bytes",
        },
        400: {"description": "Text validation error"},
        503: {"description": "TTS service unavailable"},
    },
)
async def synthesize(
    body: SynthesizeRequest,
    tts: TTSService = Depends(get_tts_service),
) -> Response:
    """Synthesise *body.text* to MP3 and return the raw bytes.

    Returns 400 if text is empty or exceeds 5 000 characters.
    Returns 503 if the TTS service is unavailable.
    """
    # Pydantic validator already rejects empty / too-long text, but the
    # endpoint performs its own check so the HTTP status codes are explicit.
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    if len(body.text) > 5000:
        raise HTTPException(
            status_code=400,
            detail="text exceeds 5000 characters",
        )

    try:
        audio_bytes = await tts.synthesize(body.text)
    except TTSError as exc:
        logger.warning("TTS synthesis failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Text-to-speech service unavailable") from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")
