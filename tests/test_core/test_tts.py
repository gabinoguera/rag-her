"""Tests for TTSService (EPIC-003 — SPEECH-02).

TDD-style: these tests describe the expected behaviour of the new
Google Cloud Text-to-Speech integration.

Mock strategy:
  - Patch "app.core.tts.TextToSpeechClient" so the real GCP client is never
    instantiated.
  - Build mock response objects that mirror the structure returned by
    google.cloud.texttospeech.TextToSpeechClient.synthesize_speech().
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.core.tts import TTSError, TTSService

# A minimal valid MP3 header (does not need to be a real audio file for tests)
FAKE_MP3_BYTES = b"\xff\xfb\x90\x00fake-mp3-content"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(audio_content: bytes = FAKE_MP3_BYTES) -> MagicMock:
    """Build a mock SynthesizeSpeechResponse."""
    mock_response = MagicMock()
    mock_response.audio_content = audio_content
    return mock_response


# ---------------------------------------------------------------------------
# TestTTSServiceSynthesize
# ---------------------------------------------------------------------------


class TestTTSServiceSynthesize:
    @pytest.mark.asyncio
    async def test_tts_returns_mp3_bytes(self) -> None:
        """synthesize() returns raw MP3 bytes on success."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.synthesize_speech.return_value = _make_mock_response()

            service = TTSService()
            result = await service.synthesize("Hola mundo")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result == FAKE_MP3_BYTES

    @pytest.mark.asyncio
    async def test_tts_empty_text_raises_tts_error(self) -> None:
        """synthesize() raises TTSError immediately when text is empty."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            service = TTSService()
            with pytest.raises(TTSError, match="[Ee]mpty|[Ee]mpty text"):
                await service.synthesize("")

            # Client must NOT be called when text is empty
            mock_client.synthesize_speech.assert_not_called()

    @pytest.mark.asyncio
    async def test_tts_whitespace_only_text_raises_tts_error(self) -> None:
        """synthesize() raises TTSError when text is whitespace only."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            service = TTSService()
            with pytest.raises(TTSError):
                await service.synthesize("   \t\n  ")

            mock_client.synthesize_speech.assert_not_called()

    @pytest.mark.asyncio
    async def test_tts_text_too_long_raises_tts_error(self) -> None:
        """synthesize() raises TTSError when text exceeds 5000 characters."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            service = TTSService()
            long_text = "a" * 5001
            with pytest.raises(TTSError, match="5000|[Ee]xceeds|[Tt]oo long"):
                await service.synthesize(long_text)

            # Client must NOT be called when text is too long
            mock_client.synthesize_speech.assert_not_called()

    @pytest.mark.asyncio
    async def test_tts_text_exactly_5000_chars_succeeds(self) -> None:
        """synthesize() accepts text of exactly 5000 characters."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.synthesize_speech.return_value = _make_mock_response()

            service = TTSService()
            result = await service.synthesize("a" * 5000)

        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_tts_api_error_raises_tts_error(self) -> None:
        """GoogleAPICallError from synthesize_speech() is re-raised as TTSError."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.synthesize_speech.side_effect = (
                google_exceptions.GoogleAPICallError("GCP internal error")
            )

            service = TTSService()
            with pytest.raises(TTSError):
                await service.synthesize("Hola mundo")

    @pytest.mark.asyncio
    async def test_tts_uses_asyncio_to_thread(self) -> None:
        """synthesize() is a coroutine (async function)."""
        service = TTSService()
        coro = service.synthesize("test")
        assert inspect.iscoroutine(coro), "synthesize must be a coroutine"
        coro.close()

    @pytest.mark.asyncio
    async def test_tts_uses_mp3_encoding(self) -> None:
        """synthesize() configures AudioConfig with MP3 encoding."""
        with patch("app.core.tts.TextToSpeechClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.synthesize_speech.return_value = _make_mock_response()

            service = TTSService()
            await service.synthesize("Hola")

        assert mock_client.synthesize_speech.called
        call_kwargs = mock_client.synthesize_speech.call_args.kwargs
        audio_config = call_kwargs.get("audio_config")
        assert audio_config is not None, "audio_config not found in call"
        from google.cloud.texttospeech import AudioEncoding
        assert audio_config.audio_encoding == AudioEncoding.MP3
