import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas.common import ErrorResponse
from app.api.schemas.search_request import SearchRequest
from app.api.schemas.search_response import SearchResponse
from app.core.embeddings import EmbeddingError
from app.core.retrieval import RetrievalService
from app.dependencies import get_retrieval_service

router = APIRouter()
logger = structlog.stdlib.get_logger()


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Empty query"},
        503: {"model": ErrorResponse, "description": "Embedding service unavailable"},
    },
)
async def search(
    body: SearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    # Extra validation: query must not be blank after stripping
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        return await retrieval_service.search(body)
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {e}",
        )
