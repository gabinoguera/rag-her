"""Google Cloud Text-to-Speech integration (EPIC-003 — SPEECH-02).

Synthesises text to MP3 audio using the Neural2-A Spanish voice.
The underlying TextToSpeechClient is synchronous; all blocking calls are
wrapped in asyncio.to_thread() to avoid blocking the event loop.

GCP hard limit for synthesis input is 5 000 characters.  We enforce this
locally before calling the API so callers receive a clear TTSError instead
of an opaque 400 from the GCP SDK.
"""

import asyncio

import structlog
from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech
from google.cloud.texttospeech import TextToSpeechClient

logger = structlog.get_logger(__name__)

_MAX_TEXT_LENGTH = 5_000


class TTSError(Exception):
    """Raised when text-to-speech synthesis fails.

    The message is safe to surface in HTTP responses — it never contains
    raw GCP error messages that might leak internal project details.
    """


class TTSService:
    """Wraps Google Cloud Text-to-Speech with an async interface.

    Args:
        language_code: BCP-47 language tag for the selected voice
            (default: "es-ES").
        voice_name: Full voice name to request from GCP TTS
            (default: "es-ES-Neural2-A").
    """

    def __init__(
        self,
        language_code: str = "es-ES",
        voice_name: str = "es-ES-Neural2-A",
    ) -> None:
        self._language_code = language_code
        self._voice_name = voice_name
        # Instantiate once; the client manages its own connection pool.
        self._client = TextToSpeechClient()

    async def synthesize(self, text: str) -> bytes:
        """Synthesise *text* to MP3 audio bytes.

        Args:
            text: Plain text to synthesise (no SSML).  Must be non-empty and
                at most 5 000 characters.

        Returns:
            Raw MP3 audio bytes suitable for streaming to an HTML5
            ``<audio>`` element.

        Raises:
            TTSError: If text is empty, too long, or the GCP API returns an
                error.  Error messages never expose raw GCP details.
        """
        if not text or not text.strip():
            raise TTSError("Empty text: text must not be empty")

        if len(text) > _MAX_TEXT_LENGTH:
            raise TTSError(
                f"Text exceeds 5000 characters limit ({len(text)} chars provided)"
            )

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=self._language_code,
            name=self._voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )

        try:
            response = await asyncio.to_thread(
                self._client.synthesize_speech,
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
        except google_exceptions.GoogleAPICallError as exc:
            logger.error("TTS API call failed", error_type=type(exc).__name__)
            raise TTSError("Text-to-speech service unavailable") from exc

        return response.audio_content  # type: ignore[no-any-return]
