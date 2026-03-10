from __future__ import annotations

from pydantic import BaseModel, Field


class Feature(BaseModel):
    """A structured feature within a functional module."""

    name: str = Field(description="Nombre corto de la feature")
    description: str = Field(description="Que hace la feature en 1-2 frases")
    user_types: list[str] = Field(
        default_factory=list,
        description="Tipos de usuario que usan esta feature",
    )


class DomainEntity(BaseModel):
    """A domain entity identified in the project."""

    name: str = Field(description="Nombre de la entidad, e.g. 'Reserva', 'Cliente'")
    description: str = Field(description="Descripcion breve de la entidad y su rol")


class FunctionalModule(BaseModel):
    """A functional module extracted from the transcription."""

    title: str = Field(description="Nombre del modulo funcional, e.g. 'Catalogo de Productos'")
    description: str = Field(description="Descripcion del modulo y su proposito")
    features: list[Feature] = Field(
        description="Features concretas con descripcion y tipos de usuario",
        min_length=1,
    )
    complexity: str = Field(
        description="Complejidad estimada del modulo: low, medium, high",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Titulos de modulos de los que depende",
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Entidades de dominio que gestiona este modulo",
    )
    search_query: str = Field(
        description="Query semantica optimizada para RAG, descriptiva y especifica para este modulo",
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
        description="Bloques funcionales identificados (incluyendo exploracion/diseno como primer modulo)",
        min_length=2,
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
    domain_entities: list[DomainEntity] = Field(
        default_factory=list,
        description="Entidades de dominio principales del proyecto",
    )
    cross_cutting_concerns: list[str] = Field(
        default_factory=list,
        description="Preocupaciones transversales: autenticacion, notificaciones, auditoria, i18n, permisos, etc.",
    )
    estimated_complexity: str = Field(
        description="Complejidad estimada del proyecto: low, medium, high, very_high"
    )
    search_queries: list[str] = Field(
        description="3-5 queries optimizadas para busqueda semantica en base de datos de presupuestos historicos",
        min_length=3,
        max_length=5,
    )
