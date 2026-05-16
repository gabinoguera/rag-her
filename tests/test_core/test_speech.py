"""Tests for STTService (EPIC-003 — SPEECH-01).

TDD-style: these tests describe the expected behaviour of the new
Google Cloud Speech-to-Text v2 integration.

Mock strategy:
  - Patch "app.core.speech.SpeechClient" so the real GCP client is never
    instantiated.
  - Build mock response objects that mirror the structure returned by
    google.cloud.speech_v2.SpeechClient.recognize().
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.core.speech import STTError, STTService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(transcript: str = "hola mundo", confidence: float = 0.95) -> MagicMock:
    """Build a mock SpeechRecognizeResponse with a single result."""
    mock_alternative = MagicMock()
    mock_alternative.transcript = transcript
    mock_alternative.confidence = confidence

    mock_result = MagicMock()
    mock_result.alternatives = [mock_alternative]

    mock_response = MagicMock()
    mock_response.results = [mock_result]
    return mock_response


def _make_empty_response() -> MagicMock:
    """Build a mock response with no results (no speech detected)."""
    mock_response = MagicMock()
    mock_response.results = []
    return mock_response


# ---------------------------------------------------------------------------
# TestSTTServiceTranscribe
# ---------------------------------------------------------------------------


class TestSTTServiceTranscribe:
    @pytest.mark.asyncio
    async def test_stt_returns_transcript(self) -> None:
        """transcribe() returns {"transcript": str, "confidence": float} on success."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.return_value = _make_mock_response("Hola mundo", 0.95)

            service = STTService(project="test-project")
            result = await service.transcribe(b"fake-audio-bytes")

        assert result["transcript"] == "Hola mundo"
        assert result["confidence"] == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_stt_empty_audio_raises_stt_error(self) -> None:
        """transcribe() raises STTError immediately when audio_bytes is empty."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            service = STTService(project="test-project")
            with pytest.raises(STTError, match="[Ee]mpty|[Ee]mpty audio"):
                await service.transcribe(b"")

            # Client must NOT be called when audio is empty
            mock_client.recognize.assert_not_called()

    @pytest.mark.asyncio
    async def test_stt_api_error_raises_stt_error(self) -> None:
        """GoogleAPICallError from recognize() is re-raised as STTError."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.side_effect = google_exceptions.GoogleAPICallError(
                "GCP internal error"
            )

            service = STTService(project="test-project")
            with pytest.raises(STTError):
                await service.transcribe(b"fake-audio-bytes")

    @pytest.mark.asyncio
    async def test_stt_uses_chirp2_model(self) -> None:
        """transcribe() configures RecognitionConfig with model='chirp_2'."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.return_value = _make_mock_response()

            service = STTService(project="test-project")
            await service.transcribe(b"fake-audio-bytes")

        # Verify recognize was called
        assert mock_client.recognize.called
        call_kwargs = mock_client.recognize.call_args
        # The request object is passed as keyword argument "request"
        request = call_kwargs.kwargs.get("request") or (
            call_kwargs.args[0] if call_kwargs.args else None
        )
        assert request is not None, "request argument not found in recognize call"
        # Access the config's model attribute
        assert request.config.model == "chirp_2"

    @pytest.mark.asyncio
    async def test_stt_uses_asyncio_to_thread(self) -> None:
        """transcribe() is a coroutine (async function)."""
        import inspect

        service = STTService(project="test-project")
        # transcribe must be an async def — calling it returns a coroutine
        coro = service.transcribe(b"x")
        assert inspect.iscoroutine(coro), "transcribe must be a coroutine"
        # Close without awaiting to avoid warnings
        coro.close()

    @pytest.mark.asyncio
    async def test_stt_no_results_raises_stt_error(self) -> None:
        """transcribe() raises STTError when response.results is empty."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.return_value = _make_empty_response()

            service = STTService(project="test-project")
            with pytest.raises(STTError, match="[Nn]o speech"):
                await service.transcribe(b"fake-audio-bytes")

    @pytest.mark.asyncio
    async def test_stt_zero_confidence_not_treated_as_error(self) -> None:
        """chirp_2 may return confidence=0.0; this is NOT an error."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.return_value = _make_mock_response("texto", 0.0)

            service = STTService(project="test-project")
            result = await service.transcribe(b"fake-audio-bytes")

        assert result["transcript"] == "texto"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_stt_language_code_override(self) -> None:
        """transcribe() accepts an optional language_code override per call."""
        with patch("app.core.speech.SpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.recognize.return_value = _make_mock_response()

            service = STTService(project="test-project", language_code="en-US")
            result = await service.transcribe(b"fake-audio-bytes", language_code="pt-BR")

        assert "transcript" in result
