"""Tests for speech endpoints (EPIC-003 — SPEECH-03 / SPEECH-04).

TDD-style: these tests describe the expected behaviour of:
  - POST /api/v1/speech/transcribe  (multipart, field "audio")
  - POST /api/v1/speech/synthesize  (JSON {"text": str}, returns audio/mpeg)

Mock strategy:
  - Override FastAPI dependency get_stt_service / get_tts_service at the
    app.dependency_overrides level so the real GCP clients are never used.
  - STTService and TTSService are replaced with AsyncMock objects.
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.core.speech import STTError
from app.core.tts import TTSError

FAKE_MP3 = b"\xff\xfb\x90\x00fake-mp3"
FAKE_AUDIO = b"\x00\x01\x02\x03fake-audio"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5433/her_poc",
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
        API_KEY="test-api-key",
        GEMINI_API_KEY="test-gemini-key",
        GOOGLE_CLOUD_PROJECT="test-project",
    )


def _make_mock_stt_service(
    transcript: str = "hola mundo",
    confidence: float = 0.9,
) -> MagicMock:
    """Return a mock STTService whose transcribe() resolves successfully."""
    svc = MagicMock()
    svc.transcribe = AsyncMock(
        return_value={"transcript": transcript, "confidence": confidence}
    )
    return svc


def _make_error_stt_service(error: Exception) -> MagicMock:
    svc = MagicMock()
    svc.transcribe = AsyncMock(side_effect=error)
    return svc


def _make_mock_tts_service(audio: bytes = FAKE_MP3) -> MagicMock:
    """Return a mock TTSService whose synthesize() resolves successfully."""
    svc = MagicMock()
    svc.synthesize = AsyncMock(return_value=audio)
    return svc


def _make_error_tts_service(error: Exception) -> MagicMock:
    svc = MagicMock()
    svc.synthesize = AsyncMock(side_effect=error)
    return svc


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Base AsyncClient fixture — no service overrides."""
    from app.db import init_db
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)
    app.dependency_overrides[get_settings] = get_test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def client_with_stt(request: pytest.FixtureRequest) -> AsyncIterator[AsyncClient]:
    """AsyncClient fixture with a mock STTService injected."""
    from app.db import init_db
    from app.dependencies import get_stt_service
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)

    mock_stt = getattr(request, "param", _make_mock_stt_service())

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_stt_service] = lambda: mock_stt

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def client_with_tts(request: pytest.FixtureRequest) -> AsyncIterator[AsyncClient]:
    """AsyncClient fixture with a mock TTSService injected."""
    from app.db import init_db
    from app.dependencies import get_tts_service
    from app.main import app

    test_settings = get_test_settings()
    init_db(test_settings)

    mock_tts = getattr(request, "param", _make_mock_tts_service())

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_tts_service] = lambda: mock_tts

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/speech/transcribe
# ---------------------------------------------------------------------------


class TestTranscribeEndpoint:
    @pytest.mark.asyncio
    async def test_transcribe_returns_transcript(self) -> None:
        """POST /transcribe with valid audio → 200 JSON {transcript, confidence}."""
        from app.db import init_db
        from app.dependencies import get_stt_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_stt = _make_mock_stt_service("Hola mundo", 0.95)
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_stt_service] = lambda: mock_stt

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/transcribe",
                files={"audio": ("test.webm", FAKE_AUDIO, "audio/webm")},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "transcript" in data
        assert "confidence" in data
        assert data["transcript"] == "Hola mundo"
        assert data["confidence"] == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_transcribe_empty_audio_returns_400(self) -> None:
        """POST /transcribe with 0-byte file → 400."""
        from app.db import init_db
        from app.dependencies import get_stt_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_stt = _make_mock_stt_service()
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_stt_service] = lambda: mock_stt

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/transcribe",
                files={"audio": ("empty.webm", b"", "audio/webm")},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_transcribe_stt_error_returns_503(self) -> None:
        """POST /transcribe when STTError is raised → 503."""
        from app.db import init_db
        from app.dependencies import get_stt_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_stt = _make_error_stt_service(STTError("Speech recognition unavailable"))
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_stt_service] = lambda: mock_stt

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/transcribe",
                files={"audio": ("audio.webm", FAKE_AUDIO, "audio/webm")},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_transcribe_missing_audio_field_returns_422(self) -> None:
        """POST /transcribe without 'audio' field → 422 FastAPI validation."""
        from app.db import init_db
        from app.dependencies import get_stt_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_stt = _make_mock_stt_service()
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_stt_service] = lambda: mock_stt

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/speech/transcribe")

        app.dependency_overrides.clear()

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/speech/synthesize
# ---------------------------------------------------------------------------


class TestSynthesizeEndpoint:
    @pytest.mark.asyncio
    async def test_synthesize_returns_mp3(self) -> None:
        """POST /synthesize with valid text → 200 audio/mpeg."""
        from app.db import init_db
        from app.dependencies import get_tts_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_tts = _make_mock_tts_service(FAKE_MP3)
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tts_service] = lambda: mock_tts

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/synthesize",
                json={"text": "Hola mundo"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "audio/mpeg" in response.headers["content-type"]
        assert response.content == FAKE_MP3

    @pytest.mark.asyncio
    async def test_synthesize_empty_text_returns_400(self) -> None:
        """POST /synthesize with empty text → 400."""
        from app.db import init_db
        from app.dependencies import get_tts_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_tts = _make_mock_tts_service()
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tts_service] = lambda: mock_tts

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/synthesize",
                json={"text": ""},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_synthesize_too_long_text_returns_400(self) -> None:
        """POST /synthesize with text > 5000 chars → 400."""
        from app.db import init_db
        from app.dependencies import get_tts_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_tts = _make_mock_tts_service()
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tts_service] = lambda: mock_tts

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/synthesize",
                json={"text": "x" * 5001},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_synthesize_tts_error_returns_503(self) -> None:
        """POST /synthesize when TTSError is raised → 503."""
        from app.db import init_db
        from app.dependencies import get_tts_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_tts = _make_error_tts_service(TTSError("TTS service unavailable"))
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tts_service] = lambda: mock_tts

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/speech/synthesize",
                json={"text": "Hola mundo"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_synthesize_no_body_returns_422(self) -> None:
        """POST /synthesize without body → 422 FastAPI validation."""
        from app.db import init_db
        from app.dependencies import get_tts_service
        from app.main import app

        test_settings = get_test_settings()
        init_db(test_settings)
        mock_tts = _make_mock_tts_service()
        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_tts_service] = lambda: mock_tts

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/speech/synthesize")

        app.dependency_overrides.clear()

        assert response.status_code == 422
