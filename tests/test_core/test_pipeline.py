import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.schemas.estimate_request import EstimateRequest
from app.api.schemas.search_response import SearchResponse, SearchResultItem
from app.config import Settings
from app.core.generation import GenerationError, GenerationService
from app.core.pipeline import EstimationPipeline, NoRelevantChunksError
from app.core.response_parser import LLMEstimationResponse


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
            "optimistic": {"days": 5, "hours": 40},
            "expected": {"days": 10, "hours": 80},
            "pessimistic": {"days": 15, "hours": 120},
        },
        estimated_cost={
            "optimistic": {"amount": 1750.0, "currency": "EUR"},
            "expected": {"amount": 3500.0, "currency": "EUR"},
            "pessimistic": {"amount": 5250.0, "currency": "EUR"},
        },
        suggested_unit_price={
            "amount": 350.0,
            "unit": "día",
            "currency": "EUR",
            "basis": "Mediana",
        },
        suggested_breakdown=[
            {"name": "Desarrollo", "days": 10, "unit_price": 350.0, "total": 3500.0},
        ],
        suggested_technologies=["Python", "FastAPI"],
        notes="Estimación de prueba.",
    )


def _make_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/estimations",
        OPENAI_API_KEY="test-key",
        EMBEDDING_MODEL="test-embedding-model",
        LLM_MODEL="gpt-4o",
    )


def _make_pipeline(
    search_results: SearchResponse | None = None,
    llm_response: LLMEstimationResponse | None = None,
    generation_error: Exception | None = None,
) -> EstimationPipeline:
    retrieval = MagicMock()
    if search_results is not None:
        retrieval.search = AsyncMock(return_value=search_results)
    else:
        retrieval.search = AsyncMock(
            return_value=_make_search_results()
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

    return EstimationPipeline(
        retrieval_service=retrieval,
        generation_service=generation,
        settings=_make_settings(),
    )


class TestPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_full_flow(self) -> None:
        pipeline = _make_pipeline()
        request = EstimateRequest(query="Desarrollo de módulo de autenticación OAuth2")

        result = await pipeline.estimate(request)

        assert result.estimation.summary == "Estimación de prueba"
        assert result.estimation.estimated_effort.expected.days == 10
        assert result.estimation.estimated_cost.expected.amount == 3500.0
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
