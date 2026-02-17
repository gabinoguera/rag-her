from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.search_request import VALID_CHUNK_TYPES


class EstimationContext(BaseModel):
    project_type: str | None = None
    technologies_preferred: list[str] | None = None
    team_size: int | None = Field(default=None, gt=0)
    complexity: str | None = Field(default=None, pattern="^(low|medium|high)$")


class EstimationOptions(BaseModel):
    chunk_types: list[str] | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)
    include_references: bool = True
    estimation_format: str = Field(default="detailed", pattern="^(summary|detailed)$")
    currency: str = Field(default="EUR", min_length=3, max_length=3)

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


class EstimateRequest(BaseModel):
    query: str = Field(min_length=10)
    context: EstimationContext | None = None
    options: EstimationOptions | None = None


class BatchQueryItem(BaseModel):
    id: str
    query: str = Field(min_length=10)
    context: EstimationContext | None = None


class BatchEstimateRequest(BaseModel):
    queries: list[BatchQueryItem] = Field(min_length=1, max_length=20)
    shared_context: EstimationContext | None = None
    options: EstimationOptions | None = None
