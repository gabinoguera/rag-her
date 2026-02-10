from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_CHUNK_TYPES = {"project_overview", "scope_block", "line_item", "phase", "team_conditions"}


class SearchFilters(BaseModel):
    chunk_types: list[str] | None = None
    technologies: list[str] | None = None
    min_cost: float | None = None
    max_cost: float | None = None
    currency: str | None = None

    @field_validator("chunk_types")
    @classmethod
    def validate_chunk_types(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - VALID_CHUNK_TYPES
            if invalid:
                raise ValueError(
                    f"Invalid chunk types: {sorted(invalid)}. "
                    f"Valid types: {sorted(VALID_CHUNK_TYPES)}"
                )
        return v


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    filters: SearchFilters | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)
