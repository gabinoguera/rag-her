from __future__ import annotations

from pydantic import BaseModel, Field

from app.api.schemas.quote_output import QuoteOutput
from app.api.schemas.transcription_analysis import TranscriptionAnalysis


class QuoteGenerationContext(BaseModel):
    """Optional context to guide quote generation."""

    client_name: str | None = Field(default=None, description="Nombre del cliente")
    client_company: str | None = Field(default=None, description="Empresa del cliente")
    currency: str = Field(default="EUR", description="Moneda del presupuesto (ISO 4217)")
    technologies_preferred: list[str] = Field(
        default_factory=list,
        description="Tecnologias preferidas para el proyecto",
    )
    team_size_hint: int | None = Field(
        default=None, description="Tamano aproximado del equipo", gt=0
    )
    budget_hint: float | None = Field(
        default=None, description="Presupuesto orientativo del cliente", gt=0
    )


class GenerateQuoteRequest(BaseModel):
    """Request body for the quote generation endpoint."""

    transcription: str = Field(
        min_length=100,
        description="Transcripcion de la reunion con el cliente (texto completo)",
    )
    context: QuoteGenerationContext | None = Field(
        default=None,
        description="Contexto adicional para guiar la generacion",
    )


class QuoteGenerationMetadata(BaseModel):
    """Metadata about the generation process."""

    reasoning_model: str = Field(description="Modelo de razonamiento utilizado")
    analysis_tokens: int = Field(description="Tokens usados en el analisis")
    generation_tokens: int = Field(description="Tokens usados en la generacion")
    rag_chunks_retrieved: int = Field(
        description="Numero de chunks RAG recuperados"
    )
    rag_queries_executed: int = Field(
        description="Numero de queries RAG ejecutadas"
    )
    analysis_time_ms: int = Field(
        description="Tiempo del paso de analisis en ms"
    )
    rag_time_ms: int = Field(description="Tiempo del paso RAG en ms")
    generation_time_ms: int = Field(
        description="Tiempo del paso de generacion en ms"
    )
    total_time_ms: int = Field(description="Tiempo total del pipeline en ms")


class GenerateQuoteResponse(BaseModel):
    """Response from the quote generation endpoint."""

    quote: QuoteOutput = Field(description="Presupuesto generado")
    analysis: TranscriptionAnalysis = Field(
        description="Analisis estructurado de la transcripcion"
    )
    metadata: QuoteGenerationMetadata = Field(
        description="Metadatos del proceso de generacion",
    )
