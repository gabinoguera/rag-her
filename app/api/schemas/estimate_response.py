from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class EffortDetail(BaseModel):
    hours: int


class EffortEstimate(BaseModel):
    optimistic: EffortDetail
    expected: EffortDetail
    pessimistic: EffortDetail


class ConfidenceFactorsResponse(BaseModel):
    references_count: int
    references_factor: float
    avg_similarity: float
    similarity_factor: float
    technology_match: float
    technology_factor: float
    cost_variance: float
    variance_factor: float


class ConfidenceScore(BaseModel):
    score: float
    level: str
    factors: ConfidenceFactorsResponse


class BreakdownTask(BaseModel):
    name: str
    hours: int


class BreakdownItem(BaseModel):
    name: str
    tasks: list[BreakdownTask]


class ReferenceItem(BaseModel):
    chunk_id: UUID
    chunk_type: str
    similarity_score: float
    project_title: str | None = None
    content_preview: str
    cost: float | None = None
    days: int | None = None
    currency: str | None = None
    technologies: list[str] | None = None


class EstimationDetail(BaseModel):
    summary: str
    estimated_effort: EffortEstimate
    confidence: ConfidenceScore
    suggested_breakdown: list[BreakdownItem]
    suggested_technologies: list[str]
    notes: str


class EstimateMetadata(BaseModel):
    query_embedding_model: str
    llm_model: str
    total_chunks_searched: int
    chunks_retrieved: int
    chunks_used_for_generation: int
    processing_time_ms: int


class EstimateResponse(BaseModel):
    estimation: EstimationDetail
    references: list[ReferenceItem]
    metadata: EstimateMetadata


class BatchEstimationItem(BaseModel):
    id: str
    estimation: EstimationDetail | None = None
    references: list[ReferenceItem] = []
    error: str | None = None


class AggregatedEstimation(BaseModel):
    total_estimated_effort: EffortEstimate
    overall_confidence: float


class BatchEstimateResponse(BaseModel):
    estimations: list[BatchEstimationItem]
    aggregated: AggregatedEstimation
    metadata: EstimateMetadata
