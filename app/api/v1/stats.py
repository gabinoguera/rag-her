from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.models import Chunk, Document, SearchLog

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    # Document counts by status
    doc_status_result = await db.execute(
        select(Document.ingestion_status, func.count())
        .group_by(Document.ingestion_status)
    )
    documents_by_status = dict(doc_status_result.all())

    # Chunk counts by type
    chunk_type_result = await db.execute(
        select(Chunk.chunk_type, func.count())
        .group_by(Chunk.chunk_type)
    )
    chunks_by_type = dict(chunk_type_result.all())

    # Search metrics (last 30 days)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    search_metrics_result = await db.execute(
        select(
            func.count().label("total_searches"),
            func.avg(SearchLog.response_time_ms).label("avg_response_time_ms"),
            func.avg(SearchLog.top_score).label("avg_top_score"),
        ).where(SearchLog.created_at >= thirty_days_ago)
    )
    search_row = search_metrics_result.one()

    search_metrics = {
        "total_searches": search_row.total_searches,
        "avg_response_time_ms": (
            round(float(search_row.avg_response_time_ms), 1)
            if search_row.avg_response_time_ms is not None
            else None
        ),
        "avg_top_score": (
            round(float(search_row.avg_top_score), 4)
            if search_row.avg_top_score is not None
            else None
        ),
    }

    return {
        "documents_by_status": documents_by_status,
        "chunks_by_type": chunks_by_type,
        "search_metrics_last_30d": search_metrics,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
    }
