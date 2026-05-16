"""Pydantic request schemas for CEO endpoints."""

from pydantic import BaseModel, Field


class CeoQueryRequest(BaseModel):
    """Request body for POST /api/v1/ceo/query."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["¿Qué bloqueos reportaron los empleados hoy?"],
        description="Pregunta del CEO en lenguaje natural.",
    )
