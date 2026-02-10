from uuid import UUID

from pydantic import BaseModel


class ChunksBreakdown(BaseModel):
    project_overview: int = 0
    scope_block: int = 0
    line_item: int = 0
    phase: int = 0
    team_conditions: int = 0


class IngestAcceptedResponse(BaseModel):
    status: str
    document_id: UUID
    message: str


class IngestStatusResponse(BaseModel):
    document_id: UUID
    status: str
    project_title: str | None = None
    chunks_created: int = 0
    processing_time_ms: int | None = None
    breakdown: ChunksBreakdown | None = None


class IngestDeleteResponse(BaseModel):
    document_id: UUID
    status: str
    chunks_deleted: int
