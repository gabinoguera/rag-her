"""TDD tests for app/api/v1/ceo.py — CEO-03 + CEO-04.

Tests are written BEFORE implementation and are expected to FAIL first.

Endpoints under test:
    POST /api/v1/ceo/query   → {answer, confidence, sources}
    GET  /api/v1/ceo/summary → {summary, checkins_count, period}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers — mock CeoService
# ---------------------------------------------------------------------------


def _make_mock_ceo_service(
    query_result: dict | None = None,
    summary_result: dict | None = None,
) -> MagicMock:
    svc = MagicMock()
    svc.query = AsyncMock(
        return_value=query_result
        or {
            "answer": "El equipo avanzó bien hoy.",
            "confidence": "alta",
            "sources": [
                {
                    "employee_name": "Ana López",
                    "date": "2026-05-16",
                    "excerpt": "Completé el módulo de pagos.",
                }
            ],
        }
    )
    svc.daily_summary = AsyncMock(
        return_value=summary_result
        or {
            "summary": "El día fue productivo.",
            "checkins_count": 3,
            "period": "hoy",
        }
    )
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def ceo_client(client_with_mock_llm: AsyncClient) -> AsyncClient:
    """Override get_ceo_service with a mock for all CEO endpoint tests."""
    from app.dependencies import get_ceo_service
    from app.main import app

    mock_svc = _make_mock_ceo_service()
    app.dependency_overrides[get_ceo_service] = lambda: mock_svc
    yield client_with_mock_llm
    # Cleanup is handled by client_with_mock_llm fixture teardown


@pytest.fixture
async def ceo_client_with_service(client_with_mock_llm: AsyncClient):
    """Return both the client and the mock service for call-count assertions."""
    from app.dependencies import get_ceo_service
    from app.main import app

    mock_svc = _make_mock_ceo_service()
    app.dependency_overrides[get_ceo_service] = lambda: mock_svc
    yield client_with_mock_llm, mock_svc


# ---------------------------------------------------------------------------
# TestCeoQueryEndpoint
# ---------------------------------------------------------------------------


class TestCeoQueryEndpoint:
    """Tests for POST /api/v1/ceo/query."""

    async def test_post_ceo_query_returns_200(self, ceo_client: AsyncClient) -> None:
        """POST /api/v1/ceo/query with valid body returns HTTP 200."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "¿Qué hicieron los empleados hoy?"},
        )
        assert resp.status_code == 200

    async def test_post_ceo_query_response_has_required_fields(self, ceo_client: AsyncClient) -> None:
        """Response body contains answer, confidence, sources."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "¿Qué proyectos avanzan?"},
        )
        data = resp.json()
        assert "answer" in data
        assert "confidence" in data
        assert "sources" in data

    async def test_post_ceo_query_confidence_is_valid_enum(self, ceo_client: AsyncClient) -> None:
        """confidence field is one of the valid enum values."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "¿Hay bloqueos?"},
        )
        assert resp.json()["confidence"] in {"alta", "media", "baja", "sin_datos"}

    async def test_post_ceo_query_sources_is_list(self, ceo_client: AsyncClient) -> None:
        """sources field is a list."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "¿Quién terminó su tarea?"},
        )
        assert isinstance(resp.json()["sources"], list)

    async def test_post_ceo_query_empty_question_returns_422(self, ceo_client: AsyncClient) -> None:
        """POST with empty question returns HTTP 422 Unprocessable Entity."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": ""},
        )
        assert resp.status_code == 422

    async def test_post_ceo_query_question_too_long_returns_422(self, ceo_client: AsyncClient) -> None:
        """POST with question > 500 chars returns HTTP 422."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "x" * 501},
        )
        assert resp.status_code == 422

    async def test_post_ceo_query_missing_question_returns_422(self, ceo_client: AsyncClient) -> None:
        """POST with no question field returns HTTP 422."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={},
        )
        assert resp.status_code == 422

    async def test_post_ceo_query_generation_error_returns_503(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        """If CeoService.query raises GenerationError, endpoint returns HTTP 503."""
        from app.core.generation import GenerationError
        from app.dependencies import get_ceo_service
        from app.main import app

        failing_svc = MagicMock()
        failing_svc.query = AsyncMock(side_effect=GenerationError("quota exceeded"))
        app.dependency_overrides[get_ceo_service] = lambda: failing_svc

        resp = await client_with_mock_llm.post(
            "/api/v1/ceo/query",
            json={"question": "¿Qué pasó hoy?"},
        )
        assert resp.status_code == 503

    async def test_post_ceo_query_delegates_to_service(
        self, ceo_client_with_service: tuple
    ) -> None:
        """POST /api/v1/ceo/query calls CeoService.query() exactly once."""
        ac, mock_svc = ceo_client_with_service
        await ac.post("/api/v1/ceo/query", json={"question": "¿Cuántos check-ins hubo?"})
        mock_svc.query.assert_called_once()

    async def test_post_ceo_query_source_item_has_fields(self, ceo_client: AsyncClient) -> None:
        """Each source item has employee_name, date, excerpt."""
        resp = await ceo_client.post(
            "/api/v1/ceo/query",
            json={"question": "¿Quién trabajó?"},
        )
        sources = resp.json()["sources"]
        if sources:
            source = sources[0]
            assert "employee_name" in source
            assert "date" in source
            assert "excerpt" in source


# ---------------------------------------------------------------------------
# TestCeoSummaryEndpoint
# ---------------------------------------------------------------------------


class TestCeoSummaryEndpoint:
    """Tests for GET /api/v1/ceo/summary."""

    async def test_get_ceo_summary_returns_200(self, ceo_client: AsyncClient) -> None:
        """GET /api/v1/ceo/summary returns HTTP 200."""
        resp = await ceo_client.get("/api/v1/ceo/summary")
        assert resp.status_code == 200

    async def test_get_ceo_summary_has_required_fields(self, ceo_client: AsyncClient) -> None:
        """Response body contains summary, checkins_count, period."""
        resp = await ceo_client.get("/api/v1/ceo/summary")
        data = resp.json()
        assert "summary" in data
        assert "checkins_count" in data
        assert "period" in data

    async def test_get_ceo_summary_checkins_count_is_integer(self, ceo_client: AsyncClient) -> None:
        """checkins_count is an integer."""
        resp = await ceo_client.get("/api/v1/ceo/summary")
        assert isinstance(resp.json()["checkins_count"], int)

    async def test_get_ceo_summary_period_value(self, ceo_client: AsyncClient) -> None:
        """period is 'hoy'."""
        resp = await ceo_client.get("/api/v1/ceo/summary")
        assert resp.json()["period"] == "hoy"

    async def test_get_ceo_summary_summary_is_string(self, ceo_client: AsyncClient) -> None:
        """summary is a non-empty string."""
        resp = await ceo_client.get("/api/v1/ceo/summary")
        summary = resp.json()["summary"]
        assert isinstance(summary, str)
        assert len(summary) > 0

    async def test_get_ceo_summary_generation_error_returns_503(
        self, client_with_mock_llm: AsyncClient
    ) -> None:
        """If CeoService.daily_summary raises GenerationError, returns HTTP 503."""
        from app.core.generation import GenerationError
        from app.dependencies import get_ceo_service
        from app.main import app

        failing_svc = MagicMock()
        failing_svc.daily_summary = AsyncMock(side_effect=GenerationError("timeout"))
        app.dependency_overrides[get_ceo_service] = lambda: failing_svc

        resp = await client_with_mock_llm.get("/api/v1/ceo/summary")
        assert resp.status_code == 503

    async def test_get_ceo_summary_delegates_to_service(
        self, ceo_client_with_service: tuple
    ) -> None:
        """GET /api/v1/ceo/summary calls CeoService.daily_summary() exactly once."""
        ac, mock_svc = ceo_client_with_service
        await ac.get("/api/v1/ceo/summary")
        mock_svc.daily_summary.assert_called_once()
