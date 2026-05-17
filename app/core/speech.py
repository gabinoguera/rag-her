"""Google Cloud Speech-to-Text v2 integration (EPIC-003 — SPEECH-01).

Uses the chirp_2 model with AutoDetectDecodingConfig so the endpoint
accepts any audio format the browser produces (webm/opus, etc.) without
requiring the caller to specify a sample rate.

The underlying SpeechClient is synchronous; all blocking calls are
wrapped in asyncio.to_thread() to avoid blocking the event loop.
"""

import asyncio

import structlog
from google.api_core import exceptions as google_exceptions
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

logger = structlog.get_logger(__name__)


class STTError(Exception):
    """Raised when speech-to-text transcription fails.

    The message is safe to surface in HTTP responses — it never contains
    raw GCP error messages that might leak internal project details.
    """


class STTService:
    """Wraps Google Cloud Speech-to-Text v2 with an async interface.

    Args:
        project: GCP project ID used to construct the recognizer resource path.
        language_code: BCP-47 language tag for recognition (default: "es-ES").
    """

    def __init__(self, project: str, language_code: str = "es-ES", model: str = "long") -> None:
        self._project = project
        self._language_code = language_code
        self._model = model
        # Instantiate once per service instance; the client manages its own
        # connection pool internally.
        self._client = SpeechClient()

    async def transcribe(
        self,
        audio_bytes: bytes,
        language_code: str | None = None,
    ) -> dict:
        """Transcribe raw audio bytes to text.

        Args:
            audio_bytes: Raw audio data (any format accepted by chirp_2 /
                AutoDetectDecodingConfig — webm/opus, wav, mp3, etc.).
            language_code: Override the service-level language code for this
                specific request.  If None, uses the language_code provided
                at construction time.

        Returns:
            A dict with keys:
              - "transcript" (str): The recognised text.
              - "confidence" (float): Score in [0.0, 1.0].  chirp_2 may return
                0.0 when confidence information is unavailable; this is NOT
                treated as an error.

        Raises:
            STTError: If audio_bytes is empty, no speech is detected, or the
                GCP API returns an error.
        """
        if not audio_bytes:
            raise STTError("Empty audio: audio_bytes must not be empty")

        effective_language = language_code or self._language_code

        config = cloud_speech.RecognitionConfig(
            model=self._model,
            language_codes=[effective_language],
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        )

        recognizer = (
            f"projects/{self._project}/locations/global/recognizers/_"
        )

        request = cloud_speech.RecognizeRequest(
            recognizer=recognizer,
            config=config,
            content=audio_bytes,
        )

        try:
            response = await asyncio.to_thread(
                self._client.recognize, request=request
            )
        except google_exceptions.GoogleAPICallError as exc:
            logger.error("STT API call failed", error_type=type(exc).__name__)
            raise STTError("Speech recognition service unavailable") from exc

        if not response.results:
            raise STTError("No speech detected in the provided audio")

        best = response.results[0].alternatives[0]
        return {
            "transcript": best.transcript,
            "confidence": float(best.confidence),
        }
