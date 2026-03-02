from __future__ import annotations

import time
from typing import Any

import structlog

from app.api.schemas.estimate_request import (
    BatchEstimateRequest,
    EstimateRequest,
    EstimationContext,
)
from app.api.schemas.estimate_response import (
    AggregatedEstimation,
    BatchEstimateResponse,
    BatchEstimationItem,
    BreakdownItem,
    BreakdownTask,
    ConfidenceFactorsResponse,
    ConfidenceScore,
    EffortDetail,
    EffortEstimate,
    EstimateMetadata,
    EstimateResponse,
    EstimationDetail,
    ReferenceItem,
)
from app.api.schemas.search_request import SearchFilters, SearchRequest
from app.api.schemas.search_response import SearchResultItem
from app.config import Settings
from app.core.confidence import ConfidenceResult, calculate_confidence
from app.core.generation import GenerationService
from app.core.query_preprocessing import preprocess_query
from app.core.response_parser import LLMEstimationResponse
from app.core.retrieval import RetrievalService

logger = structlog.stdlib.get_logger()


class NoRelevantChunksError(Exception):
    """Raised when no relevant chunks are found for a query."""


class EstimationPipeline:
    """Orchestrates the full RAG estimation pipeline."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
        settings: Settings,
    ) -> None:
        self._retrieval = retrieval_service
        self._generation = generation_service
        self._settings = settings

    async def estimate(self, request: EstimateRequest) -> EstimateResponse:
        start_time = time.monotonic()

        options = request.options or _default_options()
        currency = options.currency

        # 1. Build SearchRequest
        search_request = _build_search_request(request)

        # 2. Search
        search_response = await self._retrieval.search(search_request)

        # 3. Check results
        if search_response.total_results == 0:
            raise NoRelevantChunksError(
                "No relevant historical data found for this query"
            )

        chunks = search_response.results

        # 4. Preprocess query for detected_technologies
        preprocessed = preprocess_query(request.query)

        # 5. Generate estimation
        llm_response, chunks_used = await self._generation.generate_estimation(
            query=request.query,
            context=request.context,
            chunks=chunks,
            currency=currency,
        )

        # 6. Calculate confidence
        used_chunks = chunks[:chunks_used] if chunks_used <= len(chunks) else chunks
        confidence = calculate_confidence(
            used_chunks, preprocessed.detected_technologies
        )

        # 7. Build references
        references = _build_references(chunks, options.include_references)

        # 8. Build response
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        estimation = _build_estimation_detail(llm_response, confidence, currency)

        metadata = EstimateMetadata(
            query_embedding_model=self._settings.EMBEDDING_MODEL,
            llm_model=self._settings.LLM_MODEL,
            total_chunks_searched=search_response.total_results,
            chunks_retrieved=len(chunks),
            chunks_used_for_generation=chunks_used,
            processing_time_ms=elapsed_ms,
        )

        return EstimateResponse(
            estimation=estimation,
            references=references,
            metadata=metadata,
        )

    async def estimate_batch(
        self, request: BatchEstimateRequest
    ) -> BatchEstimateResponse:
        start_time = time.monotonic()
        options = request.options or _default_options()

        items: list[BatchEstimationItem] = []
        successful_estimations: list[EstimateResponse] = []

        for query_item in request.queries:
            merged_context = _merge_contexts(
                request.shared_context, query_item.context
            )
            single_request = EstimateRequest(
                query=query_item.query,
                context=merged_context,
                options=request.options,
            )
            try:
                result = await self.estimate(single_request)
                items.append(
                    BatchEstimationItem(
                        id=query_item.id,
                        estimation=result.estimation,
                        references=result.references,
                    )
                )
                successful_estimations.append(result)
            except Exception as e:
                await logger.awarning(
                    "Batch item failed",
                    query_id=query_item.id,
                    error=str(e),
                )
                items.append(
                    BatchEstimationItem(
                        id=query_item.id,
                        error=str(e),
                    )
                )

        aggregated = _aggregate_estimations(successful_estimations, options.currency)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        total_chunks_searched = sum(
            r.metadata.total_chunks_searched for r in successful_estimations
        )
        chunks_retrieved = sum(
            r.metadata.chunks_retrieved for r in successful_estimations
        )
        chunks_used = sum(
            r.metadata.chunks_used_for_generation for r in successful_estimations
        )

        metadata = EstimateMetadata(
            query_embedding_model=self._settings.EMBEDDING_MODEL,
            llm_model=self._settings.LLM_MODEL,
            total_chunks_searched=total_chunks_searched,
            chunks_retrieved=chunks_retrieved,
            chunks_used_for_generation=chunks_used,
            processing_time_ms=elapsed_ms,
        )

        return BatchEstimateResponse(
            estimations=items,
            aggregated=aggregated,
            metadata=metadata,
        )


# --- Helpers ---


def _default_options() -> Any:
    from app.api.schemas.estimate_request import EstimationOptions

    return EstimationOptions()


def _build_search_request(request: EstimateRequest) -> SearchRequest:
    options = request.options or _default_options()
    context = request.context

    filters = SearchFilters(
        chunk_types=options.chunk_types,
        technologies=(
            context.technologies_preferred if context else None
        ),
        currency=options.currency,
    )

    return SearchRequest(
        query=request.query,
        filters=filters,
        top_k=options.top_k,
        min_similarity=options.min_similarity,
    )


def _build_references(
    chunks: list[SearchResultItem], include: bool = True
) -> list[ReferenceItem]:
    if not include:
        return []
    refs = []
    for c in chunks:
        meta = c.metadata or {}
        days = None
        quantity = meta.get("quantity")
        unit = meta.get("unit", "")
        if quantity is not None:
            if "día" in str(unit).lower() or "day" in str(unit).lower():
                try:
                    days = int(float(str(quantity)))
                except (ValueError, TypeError):
                    pass

        refs.append(
            ReferenceItem(
                chunk_id=c.chunk_id,
                chunk_type=c.chunk_type,
                similarity_score=c.similarity_score,
                project_title=c.project_title,
                content_preview=(c.content_text or "")[:200],
                cost=c.total_cost,
                days=days,
                currency=c.currency,
                technologies=c.technologies,
            )
        )
    return refs


def _build_estimation_detail(
    llm: LLMEstimationResponse,
    confidence: ConfidenceResult,
    currency: str,
) -> EstimationDetail:
    effort = llm.estimated_effort

    def _to_dict(obj: Any) -> dict:
        if isinstance(obj, dict):
            return obj
        return obj.model_dump()

    effort_estimate = EffortEstimate(
        optimistic=EffortDetail(**_to_dict(effort["optimistic"])),
        expected=EffortDetail(**_to_dict(effort["expected"])),
        pessimistic=EffortDetail(**_to_dict(effort["pessimistic"])),
    )

    conf_factors = ConfidenceFactorsResponse(
        references_count=confidence.factors.references_count,
        references_factor=confidence.factors.references_factor,
        avg_similarity=confidence.factors.avg_similarity,
        similarity_factor=confidence.factors.similarity_factor,
        technology_match=confidence.factors.technology_match,
        technology_factor=confidence.factors.technology_factor,
        cost_variance=confidence.factors.cost_variance,
        variance_factor=confidence.factors.variance_factor,
    )

    conf_score = ConfidenceScore(
        score=confidence.score,
        level=confidence.level,
        factors=conf_factors,
    )

    breakdown = [
        BreakdownItem(
            name=item.name,
            tasks=[
                BreakdownTask(name=task.name, hours=task.hours)
                for task in item.tasks
            ],
        )
        for item in llm.suggested_breakdown
    ]

    return EstimationDetail(
        summary=llm.summary,
        estimated_effort=effort_estimate,
        confidence=conf_score,
        suggested_breakdown=breakdown,
        suggested_technologies=llm.suggested_technologies,
        notes=llm.notes,
    )


def _merge_contexts(
    shared: EstimationContext | None,
    per_query: EstimationContext | None,
) -> EstimationContext | None:
    if shared is None and per_query is None:
        return None
    if shared is None:
        return per_query
    if per_query is None:
        return shared

    return EstimationContext(
        project_type=per_query.project_type or shared.project_type,
        technologies_preferred=(
            per_query.technologies_preferred or shared.technologies_preferred
        ),
        team_size=per_query.team_size or shared.team_size,
        complexity=per_query.complexity or shared.complexity,
    )


def _aggregate_estimations(
    results: list[EstimateResponse], currency: str
) -> AggregatedEstimation:
    if not results:
        zero_effort = EffortDetail(hours=0)
        return AggregatedEstimation(
            total_estimated_effort=EffortEstimate(
                optimistic=zero_effort, expected=zero_effort, pessimistic=zero_effort
            ),
            overall_confidence=0.0,
        )

    scenarios = ["optimistic", "expected", "pessimistic"]
    effort_totals = {}

    for scenario in scenarios:
        total_hours = sum(
            getattr(r.estimation.estimated_effort, scenario).hours for r in results
        )
        effort_totals[scenario] = EffortDetail(hours=total_hours)

    avg_confidence = (
        sum(r.estimation.confidence.score for r in results) / len(results)
    )

    return AggregatedEstimation(
        total_estimated_effort=EffortEstimate(**effort_totals),
        overall_confidence=round(avg_confidence, 2),
    )
