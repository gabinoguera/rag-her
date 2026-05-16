"""Check-in endpoints — conversational 4-turn employee check-in flow."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.checkin_request import AnswerRequest
from app.api.schemas.checkin_response import (
    AnswerCheckInResponse,
    CheckInStatusResponse,
    StartCheckInResponse,
)
from app.core.embeddings import EmbeddingError
from app.dependencies import get_checkin_service
from app.services.checkin_service import (
    CheckInService,
    SessionAlreadyCompletedError,
    SessionNotFoundError,
)

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/checkin")


@router.post(
    "/start",
    response_model=StartCheckInResponse,
    summary="Start a new check-in session",
)
async def start_checkin(
    service: CheckInService = Depends(get_checkin_service),
) -> StartCheckInResponse:
    """Create a new check-in session and return the first question."""
    checkin, question_text = await service.create_session()
    return StartCheckInResponse(
        session_id=checkin.session_id,
        question_text=question_text,
    )


@router.post(
    "/{session_id}/answer",
    response_model=AnswerCheckInResponse,
    summary="Submit an answer and receive the next question",
)
async def answer_checkin(
    session_id: str,
    body: AnswerRequest,
    service: CheckInService = Depends(get_checkin_service),
) -> AnswerCheckInResponse:
    """Process one employee answer and advance the check-in conversation.

    Returns the next question, or ``is_complete=True`` with the employee's
    name when all 4 turns are done.

    Raises:
        404: session_id not found.
        409: session already completed.
        503: embedding service failure during completion.
    """
    try:
        next_question, complete, employee_name = await service.process_answer(
            session_id, body.answer_text
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SessionAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EmbeddingError as exc:
        logger.exception("embedding_error_on_complete", session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service error: {exc}",
        ) from exc

    return AnswerCheckInResponse(
        next_question_text=next_question,
        is_complete=complete,
        employee_name=employee_name,
    )


@router.get(
    "/{session_id}/status",
    response_model=CheckInStatusResponse,
    summary="Get check-in session status",
)
async def checkin_status(
    session_id: str,
    service: CheckInService = Depends(get_checkin_service),
) -> CheckInStatusResponse:
    """Return the current status of a check-in session.

    Raises:
        404: session_id not found.
    """
    try:
        checkin = await service.get_session_status(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CheckInStatusResponse(
        session_id=checkin.session_id,
        status=checkin.status,
        questions_answered=len(checkin.chunks),
        employee_name=checkin.employee.name if checkin.employee else "",
    )
