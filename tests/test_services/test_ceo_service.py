"""TDD tests for app/services/ceo_service.py — CEO-01/CEO-04.

Tests are written BEFORE implementation and are expected to FAIL first.

Target contract:
    class CeoService:
        def __init__(self, db, embedding_service, generation_service) -> None
        async def query(self, question: str) -> dict
        async def daily_summary(self) -> dict
            returns {summary: str, checkins_count: int, period: str}
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_embedding_service() -> MagicMock:
    svc = MagicMock()
    svc.generate_single_embedding = AsyncMock(return_value=[0.1] * 768)
    return svc


def _make_generation_service(answer: str = "Resumen generado.") -> MagicMock:
    svc = MagicMock()
    svc.generate = AsyncMock(return_value=answer)
    return svc


def _make_service(answer: str = "Respuesta de prueba.") -> "CeoService":  # noqa: F821
    from app.services.ceo_service import CeoService

    return CeoService(
        db=_make_db(),
        embedding_service=_make_embedding_service(),
        generation_service=_make_generation_service(answer),
    )


# ---------------------------------------------------------------------------
# TestCeoServiceInit
# ---------------------------------------------------------------------------


class TestCeoServiceInit:
    """Verify CeoService initialises correctly."""

    def test_service_stores_db(self) -> None:
        """CeoService stores the db session."""
        from app.services.ceo_service import CeoService

        db = _make_db()
        svc = CeoService(db=db, embedding_service=_make_embedding_service(), generation_service=_make_generation_service())
        assert svc._db is db

    def test_service_stores_embedding_service(self) -> None:
        """CeoService stores the embedding service."""
        from app.services.ceo_service import CeoService

        emb = _make_embedding_service()
        svc = CeoService(db=_make_db(), embedding_service=emb, generation_service=_make_generation_service())
        assert svc._embedding_service is emb

    def test_service_stores_generation_service(self) -> None:
        """CeoService stores the generation service."""
        from app.services.ceo_service import CeoService

        gen = _make_generation_service()
        svc = CeoService(db=_make_db(), embedding_service=_make_embedding_service(), generation_service=gen)
        assert svc._generation_service is gen


# ---------------------------------------------------------------------------
# TestCeoServiceQuery
# ---------------------------------------------------------------------------


class TestCeoServiceQuery:
    """Verify CeoService.query() delegates to the RAG pipeline."""

    async def test_query_delegates_to_ceo_query_module(self) -> None:
        """CeoService.query() calls app.core.ceo_query.query()."""
        from app.services.ceo_service import CeoService

        expected = {"answer": "ok", "confidence": "alta", "sources": []}
        with patch("app.services.ceo_service.rag_query", new_callable=AsyncMock, return_value=expected) as mock_rag:
            svc = CeoService(
                db=_make_db(),
                embedding_service=_make_embedding_service(),
                generation_service=_make_generation_service(),
            )
            result = await svc.query("¿Qué hicieron hoy?")
        mock_rag.assert_called_once()
        assert result == expected

    async def test_query_passes_question_to_rag(self) -> None:
        """The question text is forwarded to rag_query."""
        from app.services.ceo_service import CeoService

        with patch("app.services.ceo_service.rag_query", new_callable=AsyncMock, return_value={"answer": "x", "confidence": "alta", "sources": []}) as mock_rag:
            svc = CeoService(
                db=_make_db(),
                embedding_service=_make_embedding_service(),
                generation_service=_make_generation_service(),
            )
            await svc.query("¿Cuántos bloqueos hay?")

        call_kwargs = mock_rag.call_args
        question_arg = call_kwargs.kwargs.get("question") or call_kwargs.args[0]
        assert question_arg == "¿Cuántos bloqueos hay?"

    async def test_query_returns_dict_with_required_keys(self) -> None:
        """CeoService.query() returns a dict with answer, confidence, sources."""
        from app.services.ceo_service import CeoService

        with patch("app.services.ceo_service.rag_query", new_callable=AsyncMock, return_value={"answer": "resp", "confidence": "media", "sources": []}):
            svc = CeoService(
                db=_make_db(),
                embedding_service=_make_embedding_service(),
                generation_service=_make_generation_service(),
            )
            result = await svc.query("pregunta")

        assert "answer" in result
        assert "confidence" in result
        assert "sources" in result


# ---------------------------------------------------------------------------
# TestCeoServiceDailySummary
# ---------------------------------------------------------------------------


class TestCeoServiceDailySummary:
    """Verify CeoService.daily_summary() structure and logic."""

    async def test_daily_summary_returns_required_keys(self) -> None:
        """daily_summary() returns a dict with summary, checkins_count, period."""
        from app.services.ceo_service import CeoService

        svc = CeoService(
            db=_make_db(),
            embedding_service=_make_embedding_service(),
            generation_service=_make_generation_service(),
        )
        result = await svc.daily_summary()
        assert "summary" in result
        assert "checkins_count" in result
        assert "period" in result

    async def test_daily_summary_period_is_hoy(self) -> None:
        """period field is 'hoy' (today)."""
        from app.services.ceo_service import CeoService

        svc = CeoService(
            db=_make_db(),
            embedding_service=_make_embedding_service(),
            generation_service=_make_generation_service(),
        )
        result = await svc.daily_summary()
        assert result["period"] == "hoy"

    async def test_daily_summary_no_checkins_today(self) -> None:
        """When no completed check-ins today, checkins_count == 0 and no Gemini call."""
        from app.services.ceo_service import CeoService

        db = _make_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        gen_svc = _make_generation_service()
        svc = CeoService(db=db, embedding_service=_make_embedding_service(), generation_service=gen_svc)
        result = await svc.daily_summary()

        assert result["checkins_count"] == 0
        gen_svc.generate.assert_not_called()

    async def test_daily_summary_checkins_count_is_integer(self) -> None:
        """checkins_count is an integer."""
        from app.services.ceo_service import CeoService

        svc = CeoService(
            db=_make_db(),
            embedding_service=_make_embedding_service(),
            generation_service=_make_generation_service(),
        )
        result = await svc.daily_summary()
        assert isinstance(result["checkins_count"], int)

    async def test_daily_summary_summary_is_string(self) -> None:
        """summary is a string."""
        from app.services.ceo_service import CeoService

        svc = CeoService(
            db=_make_db(),
            embedding_service=_make_embedding_service(),
            generation_service=_make_generation_service(),
        )
        result = await svc.daily_summary()
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    async def test_daily_summary_calls_generation_when_checkins_exist(self) -> None:
        """When check-ins exist, generation_service.generate() is called."""
        from app.services.ceo_service import CeoService
        from app.models.checkin import CheckIn
        from app.models.employee import Employee
        from app.models.checkin_chunk import CheckInChunk

        # Build a minimal CheckIn mock
        employee = MagicMock(spec=Employee)
        employee.name = "Juan Pérez"

        chunk = MagicMock(spec=CheckInChunk)
        chunk.question_text = "¿Qué lograste hoy?"
        chunk.answer_text = "Completé el módulo de pagos."

        checkin = MagicMock(spec=CheckIn)
        checkin.employee = employee
        checkin.started_at = datetime.now(UTC)
        checkin.chunks = [chunk]

        db = _make_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [checkin]
        db.execute = AsyncMock(return_value=mock_result)

        gen_svc = _make_generation_service("Resumen: el equipo avanzó.")
        svc = CeoService(db=db, embedding_service=_make_embedding_service(), generation_service=gen_svc)
        result = await svc.daily_summary()

        gen_svc.generate.assert_called_once()
        assert result["checkins_count"] == 1
        assert result["summary"] == "Resumen: el equipo avanzó."
