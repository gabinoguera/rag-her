from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    chunk_id: UUID
    chunk_type: str
    similarity_score: float
    final_score: float
    content_text: str
    metadata: dict | None = None
    project_title: str | None = None
    source_document_id: UUID
    technologies: list[str] | None = None
    total_cost: float | None = None
    currency: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total_results: int
    query_processing_time_ms: int
    detected_technologies: list[str]
    suggested_chunk_types: list[str]
