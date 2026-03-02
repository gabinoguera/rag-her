"""Orchestrates the 3-step quote generation pipeline.

Step 1: Analyze transcription with reasoning model -> TranscriptionAnalysis
Step 2: RAG search using generated search queries -> list[SearchResultItem]
Step 3: Generate detailed quote with reasoning model -> QuoteOutput
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

import structlog

from app.api.schemas.quote_generation import (
    GenerateQuoteRequest,
    GenerateQuoteResponse,
    QuoteGenerationMetadata,
)
from app.api.schemas.quote_output import QuoteOutput
from app.api.schemas.search_request import SearchRequest
from app.api.schemas.search_response import SearchResultItem
from app.api.schemas.transcription_analysis import TranscriptionAnalysis
from app.core.reasoning_service import ReasoningError, ReasoningService
from app.core.retrieval import RetrievalService

logger = structlog.stdlib.get_logger()


class QuoteGenerationError(Exception):
    """Raised when the quote generation pipeline fails."""


class QuoteGenerationPipeline:
    """Orchestrates transcription analysis, RAG retrieval, and quote generation."""

    def __init__(
        self,
        reasoning_service: ReasoningService,
        retrieval_service: RetrievalService,
    ) -> None:
        self._reasoning = reasoning_service
        self._retrieval = retrieval_service

    async def generate(self, request: GenerateQuoteRequest) -> GenerateQuoteResponse:
        """Run the full 3-step pipeline."""
        pipeline_start = time.monotonic()

        context = request.context
        currency = context.currency if context else "EUR"

        # Step 1: Analyze transcription
        await logger.ainfo(
            "Starting transcription analysis",
            transcription_length=len(request.transcription),
        )
        step1_start = time.monotonic()
        try:
            analysis, analysis_tokens = await self._reasoning.analyze_transcription(
                transcription=request.transcription,
                context=context,
            )
        except ReasoningError as e:
            raise QuoteGenerationError(
                f"Transcription analysis failed: {e}"
            ) from e
        analysis_time_ms = round((time.monotonic() - step1_start) * 1000)

        await logger.ainfo(
            "Transcription analysis complete",
            project_title=analysis.project_title,
            modules_count=len(analysis.functional_modules),
            search_queries=analysis.search_queries,
            analysis_time_ms=analysis_time_ms,
        )

        # Step 2: RAG search with generated queries
        step2_start = time.monotonic()
        rag_chunks, rag_queries_executed = await self._retrieve_context(analysis)
        rag_time_ms = round((time.monotonic() - step2_start) * 1000)

        await logger.ainfo(
            "RAG retrieval complete",
            chunks_retrieved=len(rag_chunks),
            queries_executed=rag_queries_executed,
            rag_time_ms=rag_time_ms,
        )

        # Step 3: Generate QuoteOutput
        step3_start = time.monotonic()
        try:
            quote, generation_tokens = await self._reasoning.generate_quote(
                analysis=analysis,
                rag_chunks=rag_chunks,
                currency=currency,
                context=context,
            )
        except ReasoningError as e:
            raise QuoteGenerationError(
                f"Quote generation failed: {e}"
            ) from e
        generation_time_ms = round((time.monotonic() - step3_start) * 1000)

        # Inject client info from context if available
        quote = self._enrich_quote(quote, analysis, context)

        total_time_ms = round((time.monotonic() - pipeline_start) * 1000)

        await logger.ainfo(
            "Quote generation complete",
            scope_blocks=len(quote.scope_blocks),
            items=len(quote.items),
            phases=len(quote.roadmap_phases),
            total_time_ms=total_time_ms,
        )

        metadata = QuoteGenerationMetadata(
            reasoning_model=self._reasoning._model,
            analysis_tokens=analysis_tokens,
            generation_tokens=generation_tokens,
            rag_chunks_retrieved=len(rag_chunks),
            rag_queries_executed=rag_queries_executed,
            analysis_time_ms=analysis_time_ms,
            rag_time_ms=rag_time_ms,
            generation_time_ms=generation_time_ms,
            total_time_ms=total_time_ms,
        )

        return GenerateQuoteResponse(
            quote=quote,
            analysis=analysis,
            metadata=metadata,
        )

    async def _retrieve_context(
        self, analysis: TranscriptionAnalysis
    ) -> tuple[list[SearchResultItem], int]:
        """Execute multiple RAG searches using the analysis search_queries.

        Returns (deduplicated_chunks, queries_executed).
        """
        queries = analysis.search_queries
        if not queries:
            return [], 0

        # Execute all queries concurrently
        tasks = [
            self._search_single_query(query)
            for query in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect and deduplicate by chunk_id
        seen_chunk_ids: set[UUID] = set()
        all_chunks: list[SearchResultItem] = []
        queries_executed = 0

        for result in results:
            if isinstance(result, Exception):
                await logger.awarning(
                    "RAG query failed",
                    error=str(result),
                )
                continue
            queries_executed += 1
            for chunk in result:
                if chunk.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk.chunk_id)
                    all_chunks.append(chunk)

        # Sort by final_score descending and take top 15
        all_chunks.sort(key=lambda c: c.final_score, reverse=True)
        return all_chunks[:15], queries_executed

    async def _search_single_query(self, query: str) -> list[SearchResultItem]:
        """Execute a single RAG search query."""
        search_request = SearchRequest(
            query=query,
            top_k=10,
            min_similarity=0.5,
        )
        response = await self._retrieval.search(search_request)
        return response.results

    @staticmethod
    def _enrich_quote(
        quote: QuoteOutput,
        analysis: TranscriptionAnalysis,
        context: Any | None,
    ) -> QuoteOutput:
        """Enrich the quote with client info from analysis/context."""
        if quote.client is None:
            from app.api.schemas.quote_output import ClientOutput

            client_name = (
                getattr(context, "client_name", None)
                or analysis.client_name
            )
            client_company = (
                getattr(context, "client_company", None)
                or analysis.client_company
            )
            if client_name or client_company:
                quote = quote.model_copy(
                    update={
                        "client": ClientOutput(
                            name=client_name,
                            company=client_company,
                        )
                    }
                )
        return quote
