from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.search_request import SearchRequest
from app.api.schemas.search_response import SearchResponse, SearchResultItem
from app.config import Settings
from app.core.embeddings import EmbeddingService
from app.core.ranking import (
    ScoredResult,
    calculate_final_score,
    deduplicate_results,
    recency_score,
)

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

    async def search(self, request: SearchRequest) -> SearchResponse:
        start_time = time.monotonic()

        # 1. Generate query embedding with RETRIEVAL_QUERY task type
        query_embedding = await self._embedding_service.generate_single_embedding(
            request.query, task_type="RETRIEVAL_QUERY"
        )

        # 2. Build dynamic SQL — only essential filters
        where_clauses = [
            "c.embedding IS NOT NULL",
            "1 - (c.embedding <=> :query_embedding) >= :min_similarity",
        ]
        params: dict = {
            "query_embedding": str(query_embedding),
            "min_similarity": request.min_similarity,
            "top_k": request.top_k,
        }

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT c.id, c.document_id, c.chunk_type, c.content_text, c.metadata,
                   c.project_title, c.created_at,
                   1 - (c.embedding <=> :query_embedding) AS similarity
            FROM rag.chunks c
            WHERE {where_sql}
            ORDER BY c.embedding <=> :query_embedding
            LIMIT :top_k
        """)

        # 3. Execute SET LOCAL + vector search in an explicit transaction
        async with self._db.begin():
            await self._db.execute(
                text(f"SET LOCAL hnsw.ef_search = {self._settings.HNSW_EF_SEARCH}")
            )
            result = await self._db.execute(sql, params)
            rows = result.fetchall()

        # 4. Re-rank with similarity + recency weights (0.70 / 0.30)
        now = datetime.now(UTC)

        scored_results: list[ScoredResult] = []
        for row in rows:
            rec_score = recency_score(row.created_at, now)
            final = calculate_final_score(row.similarity, rec_score)

            scored_results.append(
                ScoredResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    chunk_type=row.chunk_type,
                    content_text=row.content_text,
                    metadata=row.metadata,
                    project_title=row.project_title,
                    created_at=row.created_at,
                    similarity_score=row.similarity,
                    final_score=final,
                )
            )

        # 5. Deduplicate
        deduped = deduplicate_results(scored_results)

        # 6. Calculate timing
        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 7. Build response
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
            )
            for r in deduped
        ]

        return SearchResponse(
            results=result_items,
            total_results=len(result_items),
            query_processing_time_ms=elapsed_ms,
            detected_technologies=[],
            suggested_chunk_types=[],
        )
