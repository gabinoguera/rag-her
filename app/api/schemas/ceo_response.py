"""Pydantic response schemas for CEO endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    """A single source chunk referenced in a CEO query response."""

    employee_name: str = Field(..., description="Nombre del empleado que originó el chunk.")
    date: str = Field(..., description="Fecha del check-in en formato ISO (YYYY-MM-DD).")
    excerpt: str = Field(..., description="Fragmento del check-in (máximo 200 caracteres).")


class CeoQueryResponse(BaseModel):
    """Response body for POST /api/v1/ceo/query."""

    answer: str = Field(..., description="Respuesta sintetizada por Gemini (~80 palabras).")
    confidence: Literal["alta", "media", "baja", "sin_datos"] = Field(
        ..., description="Nivel de confianza de la respuesta basado en el score de similitud."
    )
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Hasta 5 fragmentos de check-in usados para generar la respuesta.",
    )


class CeoDailySummaryResponse(BaseModel):
    """Response body for GET /api/v1/ceo/summary."""

    summary: str = Field(..., description="Resumen ejecutivo del día (~120 palabras).")
    checkins_count: int = Field(..., description="Número de check-ins completados hoy.")
    period: str = Field(..., description="Período cubierto por el resumen (siempre 'hoy').")
