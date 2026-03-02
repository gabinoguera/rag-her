from __future__ import annotations

from pydantic import BaseModel, Field


class FunctionalModule(BaseModel):
    """A functional module extracted from the transcription."""

    title: str = Field(description="Nombre del modulo funcional, e.g. 'Catalogo de Productos'")
    description: str = Field(description="Descripcion del modulo y su proposito")
    features: list[str] = Field(
        description="Features concretas mencionadas para este modulo",
        min_length=1,
    )


class Integration(BaseModel):
    """An external system integration identified in the transcription."""

    system: str = Field(description="Nombre del sistema externo, e.g. 'Holded', 'Stripe'")
    purpose: str = Field(description="Proposito de la integracion")
    complexity: str = Field(description="Complejidad estimada: low, medium, high")


class UserType(BaseModel):
    """A type of user identified in the transcription."""

    name: str = Field(description="Tipo de usuario, e.g. 'Cliente B2C', 'Admin'")
    description: str = Field(description="Descripcion del rol y permisos")


class TranscriptionAnalysis(BaseModel):
    """Structured output from Step 1: transcription analysis using a reasoning model."""

    project_title: str = Field(description="Titulo del proyecto extraido de la conversacion")
    project_description: str = Field(
        description="Descripcion general del proyecto en 2-3 frases"
    )
    client_name: str | None = Field(
        default=None, description="Nombre del cliente si se menciona"
    )
    client_company: str | None = Field(
        default=None, description="Empresa del cliente si se menciona"
    )
    functional_modules: list[FunctionalModule] = Field(
        description="Bloques funcionales identificados en la transcripcion",
        min_length=1,
    )
    integrations: list[Integration] = Field(
        default_factory=list,
        description="Integraciones con sistemas externos",
    )
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Requisitos no funcionales: rendimiento, seguridad, i18n, accesibilidad...",
    )
    user_types: list[UserType] = Field(
        default_factory=list,
        description="Tipos de usuario identificados",
    )
    admin_roles: list[str] = Field(
        default_factory=list,
        description="Roles de administracion mencionados",
    )
    technologies_mentioned: list[str] = Field(
        default_factory=list,
        description="Tecnologias mencionadas explicitamente en la conversacion",
    )
    technologies_recommended: list[str] = Field(
        default_factory=list,
        description="Tecnologias recomendadas por el equipo tecnico",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Restricciones: plazos, legales, presupuesto, etc.",
    )
    estimated_complexity: str = Field(
        description="Complejidad estimada del proyecto: low, medium, high, very_high"
    )
    search_queries: list[str] = Field(
        description="3-5 queries optimizadas para busqueda semantica en base de datos de presupuestos historicos",
        min_length=3,
        max_length=5,
    )
