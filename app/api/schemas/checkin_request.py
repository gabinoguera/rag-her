"""Request schemas for the check-in endpoints."""

from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    """Body for POST /api/v1/checkin/{session_id}/answer."""

    answer_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Employee's answer to the current check-in question.",
        examples=["Trabajé en el módulo de autenticación"],
    )
