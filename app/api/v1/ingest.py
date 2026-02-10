import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas.common import ErrorResponse
from app.api.schemas.ingest_response import (
    IngestAcceptedResponse,
    IngestDeleteResponse,
    IngestStatusResponse,
)
from app.api.schemas.quote_input import IngestRequest
from app.core.embeddings import EmbeddingError
from app.dependencies import get_ingest_service
from app.services.ingest_service import DuplicateError, IngestService

router = APIRouter()
logger = structlog.stdlib.get_logger()

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/ingest",
    response_model=IngestAcceptedResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Duplicate quote"},
        413: {"model": ErrorResponse, "description": "Payload too large"},
        503: {"model": ErrorResponse, "description": "Embedding service unavailable"},
    },
)
async def ingest_quote(
    request: Request,
    body: IngestRequest,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestAcceptedResponse:
    # Check payload size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large (max 5MB)")

    try:
        result = await ingest_service.ingest_quote(body)
        return IngestAcceptedResponse(
            status="completed",
            document_id=result.document_id,
            message=f"Quote processed: {result.chunks_count} chunks created",
        )
    except DuplicateError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate quote detected. Existing document: {e.existing_document_id}",
        )
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {e}",
        )


@router.get(
    "/ingest/{document_id}/status",
    response_model=IngestStatusResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def get_ingest_status(
    document_id: uuid.UUID,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestStatusResponse:
    result = await ingest_service.get_ingestion_status(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.delete(
    "/ingest/{document_id}",
    response_model=IngestDeleteResponse,
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
async def delete_document(
    document_id: uuid.UUID,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestDeleteResponse:
    result = await ingest_service.delete_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return result
