"""CheckInService — orchestrates the 4-turn check-in conversation.

Responsibilities:
- Create a new check-in session (Employee + CheckIn rows).
- Accept and persist employee answers turn by turn.
- On the fourth answer, vectorize all chunks in batch and mark session completed.
- Provide session status queries.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.checkin_flow import get_question, is_complete
from app.core.embeddings import EmbeddingError, EmbeddingService
from app.models.checkin import CheckIn
from app.models.checkin_chunk import CheckInChunk
from app.models.employee import Employee

logger = structlog.stdlib.get_logger()


class SessionNotFoundError(Exception):
    """Raised when a session_id does not match any CheckIn row."""


class SessionAlreadyCompletedError(Exception):
    """Raised when an answer is submitted to a completed session."""


class CheckInService:
    """Use-case orchestrator for the employee check-in flow."""

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._db = db
        self._embedding_service = embedding_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_session(self) -> tuple[CheckIn, str]:
        """Create a new check-in session.

        Returns:
            Tuple of (CheckIn ORM object, first question text).
        """
        session_id = str(uuid.uuid4())

        # Create a placeholder Employee — name will be set from the first answer.
        employee = Employee(name="")
        self._db.add(employee)
        await self._db.flush()  # obtain employee.id

        checkin = CheckIn(
            session_id=session_id,
            status="in_progress",
            employee_id=employee.id,
        )
        self._db.add(checkin)
        await self._db.flush()  # obtain checkin.id

        logger.info("checkin_session_created", session_id=session_id, employee_id=str(employee.id))
        return checkin, get_question(0)

    async def process_answer(
        self,
        session_id: str,
        answer_text: str,
    ) -> tuple[str | None, bool, str | None]:
        """Process one employee answer and advance the check-in state.

        Args:
            session_id: Unique token identifying the check-in session.
            answer_text: Raw text answer from the employee.

        Returns:
            Tuple of (next_question_text, is_complete, employee_name).
            - ``next_question_text`` is ``None`` when the session completes.
            - ``employee_name`` is set only on the completing turn.

        Raises:
            SessionNotFoundError: if *session_id* does not exist.
            SessionAlreadyCompletedError: if session status is "completed".
        """
        checkin = await self._get_checkin_with_relations(session_id)

        if checkin.status == "completed":
            raise SessionAlreadyCompletedError(
                f"Session {session_id!r} is already completed."
            )

        current_index = len(checkin.chunks)
        question_text = get_question(current_index, name=checkin.employee.name)
        clean_answer = answer_text.strip()

        # Persist the chunk for this turn.
        chunk = CheckInChunk(
            checkin_id=checkin.id,
            question_index=current_index,
            question_text=question_text,
            answer_text=clean_answer,
        )
        self._db.add(chunk)

        # First turn: capture the employee's name.
        if current_index == 0:
            checkin.employee.name = clean_answer
            logger.info("employee_name_set", name=clean_answer, session_id=session_id)

        await self._db.flush()

        next_index = current_index + 1

        if is_complete(next_index):
            await self.complete_session(session_id)
            return None, True, checkin.employee.name

        next_question = get_question(next_index, name=checkin.employee.name)
        logger.info(
            "checkin_answer_processed",
            session_id=session_id,
            current_index=current_index,
            next_index=next_index,
        )
        return next_question, False, None

    async def complete_session(self, session_id: str) -> None:
        """Vectorize all chunks and mark the session completed.

        Embeddings are generated in a single batch call to minimize latency.

        Raises:
            SessionNotFoundError: if *session_id* does not exist.
            EmbeddingError: re-raised from EmbeddingService on failure.
        """
        checkin = await self._get_checkin_with_relations(session_id)

        # Collect chunks that still need embedding (embedding is None).
        pending_chunks = [c for c in checkin.chunks if c.embedding is None]
        if pending_chunks:
            texts = [c.answer_text for c in pending_chunks]
            try:
                embeddings = await self._embedding_service.generate_embeddings(
                    texts, task_type="RETRIEVAL_DOCUMENT"
                )
            except EmbeddingError:
                logger.exception("embedding_failed", session_id=session_id)
                raise

            for chunk, embedding in zip(pending_chunks, embeddings):
                chunk.embedding = embedding

        checkin.status = "completed"
        checkin.completed_at = datetime.now(UTC)
        await self._db.flush()

        logger.info("checkin_session_completed", session_id=session_id)

    async def get_session_status(self, session_id: str) -> CheckIn:
        """Return the CheckIn with its chunks and employee loaded.

        Raises:
            SessionNotFoundError: if *session_id* does not exist.
        """
        return await self._get_checkin_with_relations(session_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_checkin_with_relations(self, session_id: str) -> CheckIn:
        stmt = (
            select(CheckIn)
            .where(CheckIn.session_id == session_id)
            .options(
                selectinload(CheckIn.chunks),
                selectinload(CheckIn.employee),
            )
        )
        result = await self._db.execute(stmt)
        checkin = result.scalar_one_or_none()
        if checkin is None:
            raise SessionNotFoundError(f"Session {session_id!r} not found.")

        # Ensure relationships are fresh (avoids stale identity-map cache within
        # the same session when chunks are added mid-conversation).
        await self._db.refresh(checkin, ["chunks", "employee"])
        return checkin
