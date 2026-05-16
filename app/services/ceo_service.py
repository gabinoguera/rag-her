"""CeoService — orchestrates CEO query and daily summary use-cases.

Responsibilities:
- Delegate RAG query to app.core.ceo_query.
- Build daily summary from today's completed check-ins.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ceo_query import query as rag_query
from app.core.embeddings import EmbeddingService
from app.core.generation import GenerationService
from app.core.prompts import CEO_DAILY_SUMMARY_PROMPT, CEO_SYSTEM_INSTRUCTION
from app.models.checkin import CheckIn
from app.models.employee import Employee

logger = structlog.stdlib.get_logger()

_NO_CHECKINS_SUMMARY = "Sin check-ins registrados hoy."


class CeoService:
    """Use-case orchestrator for CEO queries and summaries."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        generation_service: GenerationService,
    ) -> None:
        self._db = db
        self._embedding_service = embedding_service
        self._generation_service = generation_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(self, question: str) -> dict:
        """Run a RAG query on behalf of the CEO.

        Args:
            question: Natural-language question from the CEO.

        Returns:
            dict with answer, confidence, sources (delegated from ceo_query).
        """
        logger.info("ceo_service_query_start", question=question[:80])
        return await rag_query(
            question=question,
            db=self._db,
            embedding_service=self._embedding_service,
            generation_service=self._generation_service,
        )

    async def daily_summary(self) -> dict:
        """Generate an executive summary of today's completed check-ins.

        Returns:
            dict with:
                summary (str): Executive summary (~120 words).
                checkins_count (int): Number of completed check-ins today.
                period (str): Always "hoy".
        """
        from datetime import UTC, datetime

        # Query completed check-ins from today (UTC)
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = (
            select(CheckIn)
            .where(
                CheckIn.status == "completed",
                CheckIn.completed_at >= today_start,
            )
            .options(
                selectinload(CheckIn.chunks),
                selectinload(CheckIn.employee),
            )
        )
        result = await self._db.execute(stmt)
        checkins = result.scalars().all()

        checkins_count = len(checkins)
        logger.info("ceo_daily_summary_checkins", count=checkins_count)

        if checkins_count == 0:
            return {
                "summary": _NO_CHECKINS_SUMMARY,
                "checkins_count": 0,
                "period": "hoy",
            }

        # Build context from all check-in chunks
        context_lines: list[str] = []
        for checkin in checkins:
            employee_name = checkin.employee.name if checkin.employee else "Desconocido"
            date_str = checkin.started_at.date().isoformat()
            for chunk in checkin.chunks:
                context_lines.append(
                    f"[{employee_name} — {date_str}] {chunk.question_text}: {chunk.answer_text}"
                )

        context_str = "\n".join(context_lines)
        prompt = CEO_DAILY_SUMMARY_PROMPT.format(context=context_str)

        summary = await self._generation_service.generate(
            prompt, system_instruction=CEO_SYSTEM_INSTRUCTION
        )

        logger.info("ceo_daily_summary_complete", checkins_count=checkins_count)

        return {
            "summary": summary,
            "checkins_count": checkins_count,
            "period": "hoy",
        }
