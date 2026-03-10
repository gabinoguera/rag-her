from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.api.schemas.estimate_request import (
    BatchEstimateRequest,
    EstimateRequest,
    EstimationContext,
    ValidateRequest,
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
    ValidateResponse,
)
from app.api.schemas.search_request import SearchFilters, SearchRequest
from app.api.schemas.search_response import SearchResultItem
from app.config import Settings
from app.core.confidence import ConfidenceResult, calculate_confidence
from app.core.generation import GenerationService
from app.core.query_preprocessing import preprocess_query
from app.core.response_parser import LLMBreakdownItem, LLMBreakdownTask, LLMEstimationResponse, LLMValidationResponse
from app.core.retrieval import RetrievalService

logger = structlog.stdlib.get_logger()


class NoRelevantChunksError(Exception):
    """Raised when no relevant chunks are found for a query."""


@dataclass
class TaskSearchResult:
    """Result of a per-task historical search."""

    block_name: str
    task_name: str
    chunks: list[SearchResultItem] = field(default_factory=list)
    historical_hours: list[float] = field(default_factory=list)
    avg_similarity: float = 0.0


def _extract_hours_from_chunks(chunks: list[SearchResultItem]) -> list[float]:
    """Extract hours from line_item chunk metadata, normalizing days to hours."""
    hours: list[float] = []
    for c in chunks:
        meta = c.metadata or {}
        quantity = meta.get("quantity")
        unit = str(meta.get("unit", "")).lower()
        if quantity is None:
            continue
        try:
            qty = float(str(quantity))
        except (ValueError, TypeError):
            continue

        if "hora" in unit or "hour" in unit:
            hours.append(qty)
        elif "día" in unit or "dia" in unit or "day" in unit:
            hours.append(qty * 8)
        else:
            hours.append(qty * 8)
    return hours


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

    async def _search_per_task(
        self,
        breakdown: list[LLMBreakdownItem],
    ) -> list[TaskSearchResult]:
        """Perform parallel semantic searches for each task in the breakdown."""
        search_tasks = []
        task_keys: list[tuple[str, str]] = []

        for block in breakdown:
            for task in block.tasks:
                query = f"{block.name}: {task.name}"
                search_tasks.append(
                    self._retrieval.search_for_task(
                        query,
                        top_k=self._settings.TASK_VALIDATION_TOP_K,
                        min_similarity=self._settings.TASK_VALIDATION_MIN_SIMILARITY,
                    )
                )
                task_keys.append((block.name, task.name))
                if len(search_tasks) >= self._settings.MAX_TASKS_FOR_VALIDATION:
                    break
            if len(search_tasks) >= self._settings.MAX_TASKS_FOR_VALIDATION:
                break

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        task_search_results: list[TaskSearchResult] = []
        for (block_name, task_name), result in zip(task_keys, results):
            if isinstance(result, Exception):
                await logger.awarning(
                    "Per-task search failed",
                    block=block_name,
                    task=task_name,
                    error=str(result),
                )
                task_search_results.append(
                    TaskSearchResult(block_name=block_name, task_name=task_name)
                )
                continue

            chunks = result.results
            historical_hours = _extract_hours_from_chunks(chunks)
            avg_sim = (
                sum(c.similarity_score for c in chunks) / len(chunks)
                if chunks
                else 0.0
            )
            task_search_results.append(
                TaskSearchResult(
                    block_name=block_name,
                    task_name=task_name,
                    chunks=chunks,
                    historical_hours=historical_hours,
                    avg_similarity=avg_sim,
                )
            )

        return task_search_results

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

        # 5.5 Second pass: per-task validation
        validation_result: LLMValidationResponse | None = None
        task_search_results: list[TaskSearchResult] = []
        tasks_validated = 0
        tasks_with_refs = 0

        should_validate = (
            self._settings.ENABLE_TASK_VALIDATION
            and not getattr(options, "skip_validation", False)
        )

        if should_validate:
            try:
                task_search_results = await self._search_per_task(
                    llm_response.suggested_breakdown
                )
                tasks_validated = len(task_search_results)
                tasks_with_refs = sum(
                    1 for r in task_search_results if r.historical_hours
                )

                if tasks_with_refs > 0:
                    validation_result = await self._generation.validate_estimation(
                        original_breakdown=llm_response.suggested_breakdown,
                        task_references=task_search_results,
                        original_effort=llm_response.estimated_effort,
                        currency=currency,
                    )
            except Exception:
                await logger.awarning(
                    "Task validation failed, using original estimation",
                    exc_info=True,
                )

        # 6. Calculate confidence
        used_chunks = chunks[:chunks_used] if chunks_used <= len(chunks) else chunks
        confidence = calculate_confidence(
            used_chunks,
            preprocessed.detected_technologies,
            task_search_results=task_search_results or None,
        )

        # 7. Build references
        references = _build_references(
            chunks,
            options.include_references,
            task_search_results=task_search_results or None,
        )

        # 8. Build response
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        estimation = _build_estimation_detail(
            llm_response, confidence, currency, validation_result
        )

        metadata = EstimateMetadata(
            query_embedding_model=self._settings.EMBEDDING_MODEL,
            llm_model=self._settings.LLM_MODEL,
            total_chunks_searched=search_response.total_results,
            chunks_retrieved=len(chunks),
            chunks_used_for_generation=chunks_used,
            processing_time_ms=elapsed_ms,
            task_validation_enabled=self._settings.ENABLE_TASK_VALIDATION,
            tasks_validated=tasks_validated,
            tasks_with_references=tasks_with_refs,
        )

        return EstimateResponse(
            estimation=estimation,
            references=references,
            metadata=metadata,
        )

    async def validate_breakdown(self, request: ValidateRequest) -> ValidateResponse:
        """Validate hours for a user-confirmed breakdown using historical references."""
        currency = request.currency

        # Convert request breakdown to LLMBreakdownItems for _search_per_task
        breakdown = [
            LLMBreakdownItem(
                name=block.name,
                tasks=[
                    LLMBreakdownTask(name=task.name, hours=max(task.hours, 1))
                    for task in block.tasks
                ],
            )
            for block in request.breakdown
        ]

        # Search historical references per task
        task_search_results = await self._search_per_task(breakdown)
        tasks_validated = len(task_search_results)
        tasks_with_refs = sum(1 for r in task_search_results if r.historical_hours)

        # Build effort dict in the format expected by validate_estimation
        original_effort = request.estimated_effort

        validation_result: LLMValidationResponse | None = None
        if tasks_with_refs > 0:
            validation_result = await self._generation.validate_estimation(
                original_breakdown=breakdown,
                task_references=task_search_results,
                original_effort=original_effort,
                currency=currency,
            )

        if validation_result is not None:
            validated_breakdown = [
                BreakdownItem(
                    name=item.name,
                    tasks=[
                        BreakdownTask(
                            name=task.name,
                            hours=task.validated_hours,
                            original_hours=task.original_hours,
                            adjustment_reason=task.adjustment_reason,
                            references_found=task.references_found,
                        )
                        for task in item.tasks
                    ],
                )
                for item in validation_result.validated_breakdown
            ]
            effort = validation_result.estimated_effort
            effort_estimate = EffortEstimate(
                optimistic=EffortDetail(**_to_dict(effort["optimistic"])),
                expected=EffortDetail(**_to_dict(effort["expected"])),
                pessimistic=EffortDetail(**_to_dict(effort["pessimistic"])),
            )
            adjustment_notes = validation_result.adjustment_notes
        else:
            # No references found or validation failed — return original breakdown
            validated_breakdown = [
                BreakdownItem(
                    name=block.name,
                    tasks=[
                        BreakdownTask(name=task.name, hours=task.hours)
                        for task in block.tasks
                    ],
                )
                for block in breakdown
            ]
            effort_estimate = EffortEstimate(
                optimistic=EffortDetail(**_to_dict(original_effort.get("optimistic", {"hours": 0}))),
                expected=EffortDetail(**_to_dict(original_effort.get("expected", {"hours": 0}))),
                pessimistic=EffortDetail(**_to_dict(original_effort.get("pessimistic", {"hours": 0}))),
            )
            adjustment_notes = "No se encontraron referencias históricas para validar."

        return ValidateResponse(
            validated_breakdown=validated_breakdown,
            estimated_effort=effort_estimate,
            adjustment_notes=adjustment_notes,
            tasks_validated=tasks_validated,
            tasks_with_references=tasks_with_refs,
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
    chunks: list[SearchResultItem],
    include: bool = True,
    task_search_results: list[TaskSearchResult] | None = None,
    max_projects: int = 6,
) -> list[ReferenceItem]:
    if not include:
        return []

    # Collect all chunks from global + per-task searches
    all_chunks = list(chunks)
    if task_search_results:
        for tsr in task_search_results:
            all_chunks.extend(tsr.chunks)

    # Deduplicate by project: keep the chunk with the highest similarity_score per project
    best_by_project: dict[str, SearchResultItem] = {}
    for c in all_chunks:
        key = c.project_title or str(c.source_document_id)
        existing = best_by_project.get(key)
        if existing is None or c.similarity_score > existing.similarity_score:
            best_by_project[key] = c

    # Sort by similarity descending and limit
    sorted_chunks = sorted(
        best_by_project.values(),
        key=lambda c: c.similarity_score,
        reverse=True,
    )[:max_projects]

    refs = []
    for c in sorted_chunks:
        hours = _hours_from_metadata(c.metadata)
        refs.append(
            ReferenceItem(
                chunk_id=c.chunk_id,
                chunk_type=c.chunk_type,
                similarity_score=c.similarity_score,
                project_title=c.project_title,
                content_preview=(c.content_text or "")[:200],
                cost=c.total_cost,
                hours=hours,
                currency=c.currency,
                technologies=c.technologies,
            )
        )
    return refs


def _hours_from_metadata(meta: dict | None) -> int | None:
    """Convert chunk metadata quantity to hours, normalizing days to hours."""
    if not meta:
        return None
    quantity = meta.get("quantity")
    if quantity is None:
        return None
    try:
        qty = float(str(quantity))
    except (ValueError, TypeError):
        return None
    unit = str(meta.get("unit", "")).lower()
    if "hora" in unit or "hour" in unit:
        return int(qty)
    elif "día" in unit or "dia" in unit or "day" in unit:
        return int(qty * 8)
    else:
        return int(qty * 8)


def _to_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    return obj.model_dump()


def _build_estimation_detail(
    llm: LLMEstimationResponse,
    confidence: ConfidenceResult,
    currency: str,
    validation: LLMValidationResponse | None = None,
) -> EstimationDetail:
    if validation is not None:
        effort = validation.estimated_effort
    else:
        effort = llm.estimated_effort

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

    if validation is not None:
        breakdown = [
            BreakdownItem(
                name=item.name,
                tasks=[
                    BreakdownTask(
                        name=task.name,
                        hours=task.validated_hours,
                        original_hours=task.original_hours,
                        adjustment_reason=task.adjustment_reason,
                        references_found=task.references_found,
                    )
                    for task in item.tasks
                ],
            )
            for item in validation.validated_breakdown
        ]
        notes = llm.notes
        if validation.adjustment_notes:
            notes = f"{notes}\n\nNotas de validación: {validation.adjustment_notes}"
    else:
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
        notes = llm.notes

    return EstimationDetail(
        summary=llm.summary,
        estimated_effort=effort_estimate,
        confidence=conf_score,
        suggested_breakdown=breakdown,
        suggested_technologies=llm.suggested_technologies,
        notes=notes,
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
