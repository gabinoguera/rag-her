"""Response schemas for the check-in endpoints."""

from pydantic import BaseModel, Field


class StartCheckInResponse(BaseModel):
    """Response for POST /api/v1/checkin/start."""

    session_id: str = Field(
        ...,
        description="UUID string identifying the new check-in session.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    question_text: str = Field(
        ...,
        description="The first question to present to the employee.",
        examples=["¡Hola! Soy HER. ¿Cómo te llamas?"],
    )


class AnswerCheckInResponse(BaseModel):
    """Response for POST /api/v1/checkin/{session_id}/answer."""

    next_question_text: str | None = Field(
        default=None,
        description="Next question to ask. Null when the session is complete.",
        examples=["¿En qué trabajaste hoy, María?"],
    )
    is_complete: bool = Field(
        ...,
        description="True once all 4 check-in turns have been answered.",
        examples=[False],
    )
    employee_name: str | None = Field(
        default=None,
        description="Employee name — set only on the final completing turn.",
        examples=["María García"],
    )


class CheckInStatusResponse(BaseModel):
    """Response for GET /api/v1/checkin/{session_id}/status."""

    session_id: str = Field(
        ...,
        description="UUID string of the session.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    status: str = Field(
        ...,
        description="Current session status: 'in_progress' or 'completed'.",
        examples=["completed"],
    )
    questions_answered: int = Field(
        ...,
        description="Number of check-in turns completed so far (0–4).",
        examples=[4],
    )
    employee_name: str = Field(
        ...,
        description="Employee name captured on the first turn.",
        examples=["María García"],
    )
