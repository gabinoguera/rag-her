from __future__ import annotations

import re
from datetime import date
from typing import Literal

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator

logger = structlog.stdlib.get_logger()


class ClientInput(BaseModel):
    name: str | None = None
    email: str | None = None
    company: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v


class ProjectInput(BaseModel):
    title: str = Field(min_length=3)
    subtitle: str | None = None
    proposal_date: str | None = None

    @field_validator("proposal_date")
    @classmethod
    def validate_proposal_date(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("proposal_date must be a valid ISO date (YYYY-MM-DD)")
        return v


class DatesInput(BaseModel):
    issue_date: str | None = None
    valid_until: str | None = None

    @field_validator("issue_date", "valid_until")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("Date must be a valid ISO date (YYYY-MM-DD)")
        return v

    @model_validator(mode="after")
    def validate_date_order(self) -> DatesInput:
        if self.issue_date is not None and self.valid_until is not None:
            if date.fromisoformat(self.issue_date) > date.fromisoformat(self.valid_until):
                raise ValueError("issue_date must be before or equal to valid_until")
        return self


class DiscountInput(BaseModel):
    type: Literal["percentage", "fixed"]
    amount: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_percentage_range(self) -> DiscountInput:
        if self.type == "percentage" and self.amount > 100:
            raise ValueError("Percentage discount amount must be <= 100")
        return self


class ObjectiveInput(BaseModel):
    title: str
    description: str | None = None


class DetailedFeatureInput(BaseModel):
    title: str
    description: str | None = None


class ScopeBlockInput(BaseModel):
    title: str
    short_description: str
    long_description: str | None = None
    features: list[str] | None = None
    technologies: list[str] | None = None
    detailed_features: list[DetailedFeatureInput] | None = None


class RoadmapPhaseInput(BaseModel):
    name: str
    duration: str | None = None
    description: str | None = None
    deliverables: list[str] | None = None
    modules: list[str] | None = None


class ItemInput(BaseModel):
    type: Literal["service", "product", "license"]
    name: str
    description: str | None = None
    quantity: float = Field(gt=0)
    unit: str
    unit_price: float = Field(gt=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    phase: str | None = None


class TeamMemberInput(BaseModel):
    profile_type: str
    description: str | None = None
    quantity: int = Field(ge=1)
    dedication: Literal["full_time", "part_time"]


class AdditionalServiceInput(BaseModel):
    name: str
    price: float = Field(gt=0)


class ConditionsInput(BaseModel):
    payment_terms: list[str] | None = None
    included_services: list[str] | None = None
    additional_services: list[AdditionalServiceInput] | None = None


class QuoteInput(BaseModel):
    client: ClientInput | None = None
    project: ProjectInput | None = None
    dates: DatesInput | None = None
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    discount: DiscountInput | None = None
    objectives: list[ObjectiveInput] | None = None
    scope_blocks: list[ScopeBlockInput] = Field(min_length=1)
    roadmap_phases: list[RoadmapPhaseInput] | None = None
    items: list[ItemInput] = Field(min_length=1)
    team_members: list[TeamMemberInput] | None = None
    conditions: ConditionsInput | None = None
    notes: str | None = None
    terms: str | None = None

    @model_validator(mode="after")
    def validate_phase_references(self) -> QuoteInput:
        if self.roadmap_phases:
            valid_phase_names = {phase.name for phase in self.roadmap_phases}
            for item in self.items:
                if item.phase and item.phase not in valid_phase_names:
                    raise ValueError(
                        f"Item '{item.name}' references phase '{item.phase}' "
                        f"which does not exist in roadmap_phases. "
                        f"Valid phases: {sorted(valid_phase_names)}"
                    )
        return self

    @model_validator(mode="after")
    def warn_duplicate_item_names(self) -> QuoteInput:
        names = [item.name for item in self.items]
        seen: set[str] = set()
        duplicates: list[str] = []
        for name in names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            logger.warning(
                "Duplicate item names detected in quote",
                duplicates=duplicates,
            )
        return self


class IngestRequest(BaseModel):
    quote: QuoteInput
    source: str | None = None
    ingested_by: str | None = None
