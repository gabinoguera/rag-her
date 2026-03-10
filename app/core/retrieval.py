from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.search_request import SearchRequest
from app.api.schemas.search_response import SearchResponse, SearchResultItem
from app.config import Settings
from app.core.embeddings import EmbeddingService
from app.core.query_preprocessing import preprocess_query
from app.core.ranking import (
    ScoredResult,
    calculate_final_score,
    cost_range_score,
    deduplicate_results,
    recency_score,
    technology_match_score,
)
from app.models.search_log import SearchLog

logger = structlog.stdlib.get_logger()


class RetrievalService:
    """Orchestrates semantic search over chunks."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        settings: Settings,
    ) -> None:
        self._db = db
        self._embedding_service = embedding_service
        self._settings = settings

    async def search_for_task(
        self,
        task_query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> SearchResponse:
        """Targeted search for a specific task, filtered to line_item chunks."""
        from app.api.schemas.search_request import SearchFilters

        request = SearchRequest(
            query=task_query,
            filters=SearchFilters(chunk_types=["line_item"]),
            top_k=top_k,
            min_similarity=min_similarity,
        )
        return await self.search(request)

    async def search(self, request: SearchRequest) -> SearchResponse:
        start_time = time.monotonic()

        # 1. Preprocess query
        preprocessed = preprocess_query(request.query)

        # 2. Generate query embedding
        query_embedding = await self._embedding_service.generate_single_embedding(
            preprocessed.processed_text
        )

        # 3. Build query parameters outside the transaction
        filters = request.filters
        chunk_types = None
        technologies = None
        min_cost = None
        max_cost = None

        if filters:
            chunk_types = filters.chunk_types
            technologies = filters.technologies
            min_cost = filters.min_cost
            max_cost = filters.max_cost

        # Build dynamic SQL
        where_clauses = [
            "c.embedding IS NOT NULL",
            "1 - (c.embedding <=> :query_embedding) >= :min_similarity",
        ]
        params: dict = {
            "query_embedding": str(query_embedding),
            "min_similarity": request.min_similarity,
            "top_k": request.top_k,
        }

        if chunk_types:
            where_clauses.append("c.chunk_type = ANY(:chunk_types)")
            params["chunk_types"] = chunk_types

        if technologies:
            where_clauses.append("c.technologies && :technologies")
            params["technologies"] = technologies

        if min_cost is not None:
            where_clauses.append("c.total_cost >= :min_cost")
            params["min_cost"] = min_cost

        if max_cost is not None:
            where_clauses.append("c.total_cost <= :max_cost")
            params["max_cost"] = max_cost

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT c.id, c.document_id, c.chunk_type, c.content_text, c.metadata,
                   c.project_title, c.technologies, c.total_cost, c.currency, c.created_at,
                   1 - (c.embedding <=> :query_embedding) AS similarity
            FROM rag.chunks c
            WHERE {where_sql}
            ORDER BY c.embedding <=> :query_embedding
            LIMIT :top_k
        """)

        # 4. Execute SET LOCAL + vector search in an explicit transaction
        async with self._db.begin():
            await self._db.execute(
                text(f"SET LOCAL hnsw.ef_search = {self._settings.HNSW_EF_SEARCH}")
            )
            result = await self._db.execute(sql, params)
            rows = result.fetchall()

        # 5. Re-rank with composite scoring
        all_costs = [row.total_cost for row in rows if row.total_cost is not None]
        now = datetime.now(UTC)

        scored_results: list[ScoredResult] = []
        for row in rows:
            tech_score = technology_match_score(
                row.technologies, preprocessed.detected_technologies
            )
            rec_score = recency_score(row.created_at, now)
            cost_score = cost_range_score(row.total_cost, all_costs)
            final = calculate_final_score(
                row.similarity, tech_score, rec_score, cost_score
            )

            scored_results.append(
                ScoredResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    chunk_type=row.chunk_type,
                    content_text=row.content_text,
                    metadata=row.metadata,
                    project_title=row.project_title,
                    technologies=row.technologies,
                    total_cost=Decimal(str(row.total_cost)) if row.total_cost is not None else None,
                    currency=row.currency,
                    created_at=row.created_at,
                    similarity_score=row.similarity,
                    final_score=final,
                )
            )

        # 6. Deduplicate
        deduped = deduplicate_results(scored_results)

        # 7. Calculate timing
        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 8. Log search (best-effort, don't block response)
        try:
            top_score = deduped[0].final_score if deduped else None
            avg_score = (
                sum(r.final_score for r in deduped) / len(deduped)
                if deduped
                else None
            )

            search_log = SearchLog(
                query_text=preprocessed.processed_text,
                query_embedding=query_embedding,
                chunk_types_filter=chunk_types,
                technologies_filter=technologies,
                results_count=len(deduped),
                top_score=top_score,
                avg_score=avg_score,
                response_time_ms=elapsed_ms,
            )
            async with self._db.begin():
                self._db.add(search_log)
        except Exception:
            await logger.awarning("Failed to log search", exc_info=True)

        # 9. Build response
        result_items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                chunk_type=r.chunk_type,
                similarity_score=r.similarity_score,
                final_score=r.final_score,
                content_text=r.content_text,
                metadata=r.metadata,
                project_title=r.project_title,
                source_document_id=r.document_id,
                technologies=r.technologies,
                total_cost=float(r.total_cost) if r.total_cost is not None else None,
                currency=r.currency,
            )
            for r in deduped
        ]

        return SearchResponse(
            results=result_items,
            total_results=len(result_items),
            query_processing_time_ms=elapsed_ms,
            detected_technologies=preprocessed.detected_technologies,
            suggested_chunk_types=preprocessed.suggested_chunk_types,
        )
