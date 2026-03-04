import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.schemas.estimate_request import EstimateRequest, EstimationOptions, ValidateRequest
from app.api.schemas.search_response import SearchResponse, SearchResultItem
from app.config import Settings
from app.core.generation import GenerationError, GenerationService
from app.core.pipeline import (
    EstimationPipeline,
    NoRelevantChunksError,
    _extract_hours_from_chunks,
)
from app.core.response_parser import LLMEstimationResponse, LLMValidationResponse


def _make_search_results(count: int = 5) -> SearchResponse:
    results = []
    for i in range(count):
        results.append(
            SearchResultItem(
                chunk_id=uuid.uuid4(),
                chunk_type="scope_block",
                similarity_score=0.85 - i * 0.02,
                final_score=0.80 - i * 0.02,
                content_text=f"Desarrollo módulo {i + 1}",
                metadata={"related_items": [f"Item {i + 1}"]},
                project_title=f"Proyecto {i + 1}",
                source_document_id=uuid.uuid4(),
                technologies=["Python", "FastAPI"],
                total_cost=1000.0 + i * 200,
                currency="EUR",
            )
        )
    return SearchResponse(
        results=results,
        total_results=count,
        query_processing_time_ms=50,
        detected_technologies=["Python", "FastAPI"],
        suggested_chunk_types=["scope_block"],
    )


def _make_valid_llm_response() -> LLMEstimationResponse:
    return LLMEstimationResponse(
        summary="Estimación de prueba",
        estimated_effort={
            "optimistic": {"hours": 40},
            "expected": {"hours": 80},
            "pessimistic": {"hours": 120},
        },
        suggested_breakdown=[
            {
                "name": "Desarrollo",
                "tasks": [
                    {"name": "Implementación de lógica", "hours": 40},
                    {"name": "Testing unitario", "hours": 24},
                    {"name": "Documentación técnica", "hours": 16},
                ],
            },
        ],
        suggested_technologies=["Python", "FastAPI"],
        notes="Estimación de prueba.",
    )


def _make_line_item_search_results(count: int = 3) -> SearchResponse:
    results = []
    for i in range(count):
        results.append(
            SearchResultItem(
                chunk_id=uuid.uuid4(),
                chunk_type="line_item",
                similarity_score=0.75 - i * 0.05,
                final_score=0.70 - i * 0.05,
                content_text=f"Tarea individual {i + 1}",
                metadata={
                    "item_name": f"Task {i + 1}",
                    "quantity": 5 + i,
                    "unit": "días",
                    "unit_price": 350,
                    "total_price": (5 + i) * 350,
                },
                project_title=f"Proyecto {i + 1}",
                source_document_id=uuid.uuid4(),
                technologies=["Python"],
                total_cost=(5 + i) * 350.0,
                currency="EUR",
            )
        )
    return SearchResponse(
        results=results,
        total_results=count,
        query_processing_time_ms=30,
        detected_technologies=["Python"],
        suggested_chunk_types=["line_item"],
    )


def _make_validation_response() -> LLMValidationResponse:
    return LLMValidationResponse(
        validated_breakdown=[
            {
                "name": "Desarrollo",
                "tasks": [
                    {
                        "name": "Implementación de lógica",
                        "original_hours": 40,
                        "validated_hours": 48,
                        "adjustment_reason": "Datos históricos sugieren más horas",
                        "references_found": 3,
                    },
                    {
                        "name": "Testing unitario",
                        "original_hours": 24,
                        "validated_hours": 24,
                        "adjustment_reason": None,
                        "references_found": 0,
                    },
                    {
                        "name": "Documentación técnica",
                        "original_hours": 16,
                        "validated_hours": 16,
                        "adjustment_reason": None,
                        "references_found": 0,
                    },
                ],
            },
        ],
        estimated_effort={
            "optimistic": {"hours": 48},
            "expected": {"hours": 88},
            "pessimistic": {"hours": 130},
        },
        adjustment_notes="Se ajustó la tarea de implementación.",
    )


def _make_settings(enable_validation: bool = True) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/estimations",
        OPENAI_API_KEY="test-key",
        EMBEDDING_MODEL="test-embedding-model",
        LLM_MODEL="gpt-4o",
        ENABLE_TASK_VALIDATION=enable_validation,
    )


def _make_pipeline(
    search_results: SearchResponse | None = None,
    llm_response: LLMEstimationResponse | None = None,
    generation_error: Exception | None = None,
    enable_validation: bool = True,
    task_search_results: SearchResponse | None = None,
    validation_response: LLMValidationResponse | None = None,
) -> EstimationPipeline:
    retrieval = MagicMock()

    if task_search_results is not None:
        # First call: global search, subsequent calls: per-task search
        global_results = search_results if search_results is not None else _make_search_results()
        retrieval.search = AsyncMock(return_value=global_results)
        retrieval.search_for_task = AsyncMock(return_value=task_search_results)
    else:
        if search_results is not None:
            retrieval.search = AsyncMock(return_value=search_results)
        else:
            retrieval.search = AsyncMock(return_value=_make_search_results())
        retrieval.search_for_task = AsyncMock(
            return_value=SearchResponse(
                results=[],
                total_results=0,
                query_processing_time_ms=10,
                detected_technologies=[],
                suggested_chunk_types=[],
            )
        )

    generation = MagicMock(spec=GenerationService)
    if generation_error is not None:
        generation.generate_estimation = AsyncMock(side_effect=generation_error)
    elif llm_response is not None:
        generation.generate_estimation = AsyncMock(
            return_value=(llm_response, 5)
        )
    else:
        generation.generate_estimation = AsyncMock(
            return_value=(_make_valid_llm_response(), 5)
        )

    if validation_response is not None:
        generation.validate_estimation = AsyncMock(return_value=validation_response)
    else:
        generation.validate_estimation = AsyncMock(return_value=None)

    return EstimationPipeline(
        retrieval_service=retrieval,
        generation_service=generation,
        settings=_make_settings(enable_validation=enable_validation),
    )


class TestPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_full_flow(self) -> None:
        pipeline = _make_pipeline()
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        assert result.estimation.summary == "Estimación de prueba"
        assert result.estimation.estimated_effort.expected.hours == 80
        assert result.estimation.confidence.score > 0
        assert len(result.references) > 0
        assert result.metadata.llm_model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_pipeline_no_results(self) -> None:
        empty_response = SearchResponse(
            results=[],
            total_results=0,
            query_processing_time_ms=10,
            detected_technologies=[],
            suggested_chunk_types=[],
        )
        pipeline = _make_pipeline(search_results=empty_response)
        request = EstimateRequest(query="Algo que no tiene resultados históricos")

        with pytest.raises(NoRelevantChunksError):
            await pipeline.estimate(request)

    @pytest.mark.asyncio
    async def test_pipeline_llm_timeout(self) -> None:
        pipeline = _make_pipeline(
            generation_error=GenerationError("LLM timeout")
        )
        request = EstimateRequest(query="Desarrollo de módulo de pagos Stripe")

        with pytest.raises(GenerationError):
            await pipeline.estimate(request)

    @pytest.mark.asyncio
    async def test_pipeline_fallback(self) -> None:
        fallback_response = GenerationService.build_fallback_estimation(
            _make_search_results().results, "EUR"
        )
        pipeline = _make_pipeline(llm_response=fallback_response)
        request = EstimateRequest(query="Estimación con fallback estadístico")

        result = await pipeline.estimate(request)

        assert "fallback" in result.estimation.notes.lower() or "degradada" in result.estimation.notes.lower()


class TestPipelineValidation:
    @pytest.mark.asyncio
    async def test_validation_full_flow(self) -> None:
        """When per-task search finds refs and validation succeeds, use validated hours."""
        pipeline = _make_pipeline(
            task_search_results=_make_line_item_search_results(),
            validation_response=_make_validation_response(),
        )
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        # Should use validated hours
        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].hours == 48  # validated_hours
        assert tasks[0].original_hours == 40
        assert tasks[0].adjustment_reason is not None
        assert tasks[0].references_found == 3
        assert result.metadata.task_validation_enabled is True
        assert result.metadata.tasks_validated > 0
        assert result.metadata.tasks_with_references > 0

    @pytest.mark.asyncio
    async def test_validation_no_references(self) -> None:
        """When per-task search finds no refs, skip validation and use original."""
        pipeline = _make_pipeline()  # default: empty per-task results
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        # Should use original hours (no validation happened)
        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].hours == 40
        assert tasks[0].original_hours is None
        assert result.metadata.task_validation_enabled is True
        assert result.metadata.tasks_with_references == 0

    @pytest.mark.asyncio
    async def test_validation_disabled(self) -> None:
        """When ENABLE_TASK_VALIDATION is False, skip entire second pass."""
        pipeline = _make_pipeline(enable_validation=False)
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        assert result.metadata.task_validation_enabled is False
        assert result.metadata.tasks_validated == 0
        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].original_hours is None

    @pytest.mark.asyncio
    async def test_validation_llm_failure_uses_original(self) -> None:
        """When validation LLM call fails (returns None), use original estimation."""
        pipeline = _make_pipeline(
            task_search_results=_make_line_item_search_results(),
            validation_response=None,  # LLM failed
        )
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].hours == 40  # original hours
        assert tasks[0].original_hours is None
        assert result.metadata.tasks_with_references > 0  # searches happened


class TestExtractHoursFromChunks:
    def test_extract_days_to_hours(self) -> None:
        chunks = [
            MagicMock(metadata={"quantity": 5, "unit": "días"}),
            MagicMock(metadata={"quantity": 3, "unit": "days"}),
        ]
        hours = _extract_hours_from_chunks(chunks)
        assert hours == [40.0, 24.0]

    def test_extract_hours_directly(self) -> None:
        chunks = [
            MagicMock(metadata={"quantity": 16, "unit": "horas"}),
            MagicMock(metadata={"quantity": 8, "unit": "hours"}),
        ]
        hours = _extract_hours_from_chunks(chunks)
        assert hours == [16.0, 8.0]

    def test_skip_missing_quantity(self) -> None:
        chunks = [
            MagicMock(metadata={"unit": "días"}),
            MagicMock(metadata={}),
        ]
        hours = _extract_hours_from_chunks(chunks)
        assert hours == []

    def test_empty_chunks(self) -> None:
        assert _extract_hours_from_chunks([]) == []


class TestSkipValidation:
    @pytest.mark.asyncio
    async def test_skip_validation_skips_second_pass(self) -> None:
        """When skip_validation=True, the per-task validation is skipped even if enabled."""
        pipeline = _make_pipeline(
            task_search_results=_make_line_item_search_results(),
            validation_response=_make_validation_response(),
        )
        request = EstimateRequest(
            query="Desarrollo de módulo de autenticación OAuth2",
            options=EstimationOptions(skip_validation=True),
        )

        result = await pipeline.estimate(request)

        # Should use original hours, not validated
        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].hours == 40  # original, not 48
        assert tasks[0].original_hours is None
        assert result.metadata.tasks_validated == 0

    @pytest.mark.asyncio
    async def test_skip_validation_false_runs_validation(self) -> None:
        """When skip_validation=False (default), validation runs normally."""
        pipeline = _make_pipeline(
            task_search_results=_make_line_item_search_results(),
            validation_response=_make_validation_response(),
        )
        request = EstimateRequest(
            query="Desarrollo de módulo de autenticación OAuth2",
            options=EstimationOptions(skip_validation=False),
        )

        result = await pipeline.estimate(request)

        tasks = result.estimation.suggested_breakdown[0].tasks
        assert tasks[0].hours == 48  # validated


class TestValidateBreakdown:
    @pytest.mark.asyncio
    async def test_validate_breakdown_with_references(self) -> None:
        """validate_breakdown returns validated hours when references are found."""
        pipeline = _make_pipeline(
            task_search_results=_make_line_item_search_results(),
            validation_response=_make_validation_response(),
        )
        request = ValidateRequest(
            breakdown=[
                {
                    "name": "Desarrollo",
                    "tasks": [
                        {"name": "Implementación de lógica", "hours": 40},
                        {"name": "Testing unitario", "hours": 24},
                        {"name": "Documentación técnica", "hours": 16},
                    ],
                }
            ],
            estimated_effort={
                "optimistic": {"hours": 40},
                "expected": {"hours": 80},
                "pessimistic": {"hours": 120},
            },
        )

        result = await pipeline.validate_breakdown(request)

        assert result.tasks_validated > 0
        assert result.tasks_with_references > 0
        assert result.validated_breakdown[0].tasks[0].hours == 48
        assert result.validated_breakdown[0].tasks[0].original_hours == 40
        assert result.adjustment_notes == "Se ajustó la tarea de implementación."

    @pytest.mark.asyncio
    async def test_validate_breakdown_no_references(self) -> None:
        """validate_breakdown returns original hours when no references are found."""
        pipeline = _make_pipeline()  # default: empty per-task results
        request = ValidateRequest(
            breakdown=[
                {
                    "name": "Desarrollo",
                    "tasks": [
                        {"name": "Tarea nueva", "hours": 20},
                    ],
                }
            ],
            estimated_effort={
                "optimistic": {"hours": 16},
                "expected": {"hours": 20},
                "pessimistic": {"hours": 30},
            },
        )

        result = await pipeline.validate_breakdown(request)

        assert result.tasks_with_references == 0
        assert result.validated_breakdown[0].tasks[0].hours == 20
        assert "No se encontraron" in result.adjustment_notes

    @pytest.mark.asyncio
    async def test_validate_breakdown_zero_hours_task(self) -> None:
        """Tasks with 0 hours are normalized to 1 for search."""
        pipeline = _make_pipeline()
        request = ValidateRequest(
            breakdown=[
                {
                    "name": "Bloque",
                    "tasks": [{"name": "Tarea nueva", "hours": 0}],
                }
            ],
            estimated_effort={
                "optimistic": {"hours": 0},
                "expected": {"hours": 0},
                "pessimistic": {"hours": 0},
            },
        )

        result = await pipeline.validate_breakdown(request)

        # Should not crash, returns original hours
        assert result.tasks_validated > 0
