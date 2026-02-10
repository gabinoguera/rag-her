import time
from typing import Any

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db import get_session_factory

router = APIRouter()
logger = structlog.stdlib.get_logger()


@router.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()

    db_status: dict[str, Any] = {"status": "unavailable"}
    pgvector_status: dict[str, Any] = {"status": "unavailable"}

    try:
        factory = get_session_factory()
        async with factory() as session:
            # Check database connectivity with latency
            start = time.monotonic()
            await session.execute(text("SELECT 1"))
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            db_status = {"status": "healthy", "latency_ms": latency_ms}

            # Check pgvector extension
            result = await session.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.scalar_one_or_none()
            if row:
                pgvector_status = {"status": "healthy", "version": row}
            else:
                pgvector_status = {"status": "unavailable", "error": "extension not installed"}
    except Exception as e:
        await logger.awarning("Health check dependency failure", error=str(e))
        if db_status["status"] != "healthy":
            db_status = {"status": "unavailable", "error": str(e)}

    all_healthy = db_status["status"] == "healthy" and pgvector_status["status"] == "healthy"
    overall_status = "healthy" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "dependencies": {
            "database": db_status,
            "pgvector": pgvector_status,
        },
    }
