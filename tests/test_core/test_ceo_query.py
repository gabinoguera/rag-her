"""TDD tests for app/core/ceo_query.py — CEO-01.

Tests are written BEFORE implementation and are expected to FAIL first.

Target contract:
    async def query(
        question: str,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        generation_service: GenerationService,
        top_k: int = 10,
        min_similarity: float = 0.30,
    ) -> dict:
        Returns {answer, confidence, sources: [{employee_name, date, excerpt}]}
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_row(
    employee_name: str = "Ana López",
    answer_text: str = "Terminé la integración con el API.",
    similarity: float = 0.85,
    days_ago: int = 1,
) -> dict:
    """Return a plain dict that mimics a SQLAlchemy RowMapping."""
    ts = datetime.now(UTC) - timedelta(days=days_ago)
    return {
        "id": uuid.uuid4(),
        "employee_name": employee_name,
        "answer_text": answer_text,
        "question_text": "¿Qué lograste hoy?",
        "created_at": ts,
        "started_at": ts,
        "similarity": similarity,
    }


def _make_mock_db(rows: list[Any] | None = None) -> AsyncMock:
    """Build a mock AsyncSession whose execute() returns the given rows."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    if rows is None:
        rows = []
    mock_result.mappings.return_value.all.return_value = rows
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_mock_embedding_service(embedding: list[float] | None = None) -> MagicMock:
    service = MagicMock()
    service.generate_single_embedding = AsyncMock(
        return_value=embedding or [0.1] * 768
    )
    return service


def _make_mock_generation_service(answer: str = "Respuesta de prueba.") -> MagicMock:
    service = MagicMock()
    service.generate = AsyncMock(return_value=answer)
    return service


# ---------------------------------------------------------------------------
# TestCeoQueryReturnStructure
# ---------------------------------------------------------------------------


class TestCeoQueryReturnStructure:
    """Verify the return dict structure of ceo_query.query()."""

    async def test_returns_dict_with_required_keys(self) -> None:
        """query() returns a dict with keys: answer, confidence, sources."""
        from app.core.ceo_query import query

        rows = [_make_mock_row()]
        result = await query(
            question="¿Qué hicieron los empleados hoy?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert "answer" in result
        assert "confidence" in result
        assert "sources" in result

    async def test_answer_is_string(self) -> None:
        """The answer field is a string."""
        from app.core.ceo_query import query

        rows = [_make_mock_row()]
        result = await query(
            question="¿Qué bloqueos hay?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service("Respuesta generada."),
        )
        assert isinstance(result["answer"], str)

    async def test_sources_is_list(self) -> None:
        """sources is a list."""
        from app.core.ceo_query import query

        rows = [_make_mock_row()]
        result = await query(
            question="¿Qué proyectos están activos?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert isinstance(result["sources"], list)

    async def test_source_item_has_required_fields(self) -> None:
        """Each source item has employee_name, date, excerpt."""
        from app.core.ceo_query import query

        rows = [_make_mock_row(employee_name="Carlos Ruiz", answer_text="Completé el deploy.")]
        result = await query(
            question="¿Quién hizo deploy?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert len(result["sources"]) >= 1
        source = result["sources"][0]
        assert "employee_name" in source
        assert "date" in source
        assert "excerpt" in source

    async def test_source_employee_name_matches_row(self) -> None:
        """employee_name in source matches the row data."""
        from app.core.ceo_query import query

        rows = [_make_mock_row(employee_name="María García")]
        result = await query(
            question="¿Quién trabajó hoy?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert result["sources"][0]["employee_name"] == "María García"

    async def test_source_date_is_iso_format(self) -> None:
        """date in source is ISO-formatted string YYYY-MM-DD."""
        from app.core.ceo_query import query

        rows = [_make_mock_row()]
        result = await query(
            question="¿Qué logros hay?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        date_str = result["sources"][0]["date"]
        # Should be parseable as ISO date
        from datetime import date
        parsed = date.fromisoformat(date_str)
        assert isinstance(parsed, date)

    async def test_source_excerpt_from_answer_text(self) -> None:
        """excerpt contains (part of) the answer_text."""
        from app.core.ceo_query import query

        answer_text = "Completé la revisión de código del módulo de pagos."
        rows = [_make_mock_row(answer_text=answer_text)]
        result = await query(
            question="¿Qué revisiones se hicieron?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        # The excerpt should contain the answer_text or a prefix of it
        excerpt = result["sources"][0]["excerpt"]
        assert answer_text[:50] in excerpt or excerpt in answer_text


# ---------------------------------------------------------------------------
# TestCeoQueryConfidence
# ---------------------------------------------------------------------------


class TestCeoQueryConfidence:
    """Verify confidence heuristic based on top-1 final_score."""

    async def test_high_confidence_when_top_score_gte_070(self) -> None:
        """confidence == 'alta' when top-1 final_score >= 0.70."""
        from app.core.ceo_query import query

        # similarity=0.95 + recency~1.0 → final ~ 0.95*0.70+0.30 >> 0.70
        rows = [_make_mock_row(similarity=0.95, days_ago=0)]
        result = await query(
            question="¿Cómo va el equipo?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert result["confidence"] == "alta"

    async def test_low_confidence_when_top_score_lt_045(self) -> None:
        """confidence == 'baja' when top-1 final_score < 0.45."""
        from app.core.ceo_query import query

        # similarity=0.31 (just above min), very old → final << 0.45
        rows = [_make_mock_row(similarity=0.31, days_ago=365)]
        result = await query(
            question="¿Hay bloqueos?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert result["confidence"] == "baja"

    async def test_sin_datos_confidence_when_no_chunks(self) -> None:
        """confidence == 'sin_datos' when no rows returned from DB."""
        from app.core.ceo_query import query

        result = await query(
            question="¿Qué logros hay?",
            db=_make_mock_db([]),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert result["confidence"] == "sin_datos"

    async def test_confidence_values_are_valid(self) -> None:
        """confidence is always one of the valid enum values."""
        from app.core.ceo_query import query

        valid = {"alta", "media", "baja", "sin_datos"}
        for rows in [[], [_make_mock_row(similarity=0.31, days_ago=365)], [_make_mock_row()]]:
            result = await query(
                question="pregunta",
                db=_make_mock_db(rows),
                embedding_service=_make_mock_embedding_service(),
                generation_service=_make_mock_generation_service(),
            )
            assert result["confidence"] in valid


# ---------------------------------------------------------------------------
# TestCeoQueryNoChunks
# ---------------------------------------------------------------------------


class TestCeoQueryNoChunks:
    """When no chunks are found, return early without calling Gemini."""

    async def test_no_chunks_returns_empty_sources(self) -> None:
        """When no chunks found, sources == []."""
        from app.core.ceo_query import query

        result = await query(
            question="¿Qué hicieron hoy?",
            db=_make_mock_db([]),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert result["sources"] == []

    async def test_no_chunks_does_not_call_generation_service(self) -> None:
        """When no chunks found, GenerationService.generate() is NOT called."""
        from app.core.ceo_query import query

        gen_service = _make_mock_generation_service()
        await query(
            question="¿Qué hicieron hoy?",
            db=_make_mock_db([]),
            embedding_service=_make_mock_embedding_service(),
            generation_service=gen_service,
        )
        gen_service.generate.assert_not_called()

    async def test_no_chunks_answer_is_not_empty_string(self) -> None:
        """When no chunks found, answer is a non-empty fallback string."""
        from app.core.ceo_query import query

        result = await query(
            question="¿Qué logros hay?",
            db=_make_mock_db([]),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0


# ---------------------------------------------------------------------------
# TestCeoQueryEmbeddingUsage
# ---------------------------------------------------------------------------


class TestCeoQueryEmbeddingUsage:
    """Verify how query() calls the embedding service."""

    async def test_uses_retrieval_query_task_type(self) -> None:
        """generate_single_embedding is called with task_type='RETRIEVAL_QUERY'."""
        from app.core.ceo_query import query

        emb_service = _make_mock_embedding_service()
        await query(
            question="¿Cómo avanza el proyecto?",
            db=_make_mock_db([]),
            embedding_service=emb_service,
            generation_service=_make_mock_generation_service(),
        )
        emb_service.generate_single_embedding.assert_called_once()
        call_kwargs = emb_service.generate_single_embedding.call_args
        task_type = call_kwargs.kwargs.get("task_type") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert task_type == "RETRIEVAL_QUERY"

    async def test_question_passed_to_embedding_service(self) -> None:
        """The question text is passed to generate_single_embedding."""
        from app.core.ceo_query import query

        emb_service = _make_mock_embedding_service()
        await query(
            question="¿Qué bloqueos hay hoy?",
            db=_make_mock_db([]),
            embedding_service=emb_service,
            generation_service=_make_mock_generation_service(),
        )
        call_args = emb_service.generate_single_embedding.call_args
        text_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("text")
        assert text_arg == "¿Qué bloqueos hay hoy?"


# ---------------------------------------------------------------------------
# TestCeoQuerySourceLimits
# ---------------------------------------------------------------------------


class TestCeoQuerySourceLimits:
    """Verify sources are limited and excerpts are truncated."""

    async def test_sources_limited_to_5(self) -> None:
        """sources contains at most 5 items regardless of how many rows exist."""
        from app.core.ceo_query import query

        rows = [_make_mock_row(employee_name=f"Emp{i}", similarity=0.9 - i * 0.01) for i in range(10)]
        result = await query(
            question="¿Qué hicieron todos?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert len(result["sources"]) <= 5

    async def test_excerpt_limited_to_200_chars(self) -> None:
        """excerpt is at most 200 characters long."""
        from app.core.ceo_query import query

        long_answer = "x" * 500
        rows = [_make_mock_row(answer_text=long_answer)]
        result = await query(
            question="¿Qué se hizo?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(),
        )
        assert len(result["sources"][0]["excerpt"]) <= 200


# ---------------------------------------------------------------------------
# TestCeoQueryGenerationCall
# ---------------------------------------------------------------------------


class TestCeoQueryGenerationCall:
    """Verify how query() calls the generation service."""

    async def test_generation_called_when_chunks_available(self) -> None:
        """GenerationService.generate() is called when there are valid chunks."""
        from app.core.ceo_query import query

        gen_service = _make_mock_generation_service()
        rows = [_make_mock_row()]
        await query(
            question="¿Qué proyectos avanzan?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=gen_service,
        )
        gen_service.generate.assert_called_once()

    async def test_generation_answer_is_returned(self) -> None:
        """The answer returned by generation_service.generate() is in the result."""
        from app.core.ceo_query import query

        expected_answer = "El equipo avanzó significativamente en el proyecto principal."
        rows = [_make_mock_row()]
        result = await query(
            question="¿Cómo va el equipo?",
            db=_make_mock_db(rows),
            embedding_service=_make_mock_embedding_service(),
            generation_service=_make_mock_generation_service(expected_answer),
        )
        assert result["answer"] == expected_answer
