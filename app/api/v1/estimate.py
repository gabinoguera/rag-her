import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas.common import ErrorResponse
from app.api.schemas.estimate_request import BatchEstimateRequest, EstimateRequest, ValidateRequest
from app.api.schemas.estimate_response import BatchEstimateResponse, EstimateResponse, ValidateResponse
from app.core.embeddings import EmbeddingError
from app.core.generation import GenerationError
from app.core.pipeline import EstimationPipeline, NoRelevantChunksError
from app.dependencies import get_estimation_pipeline

router = APIRouter()
logger = structlog.stdlib.get_logger()


@router.post(
    "/estimate",
    response_model=EstimateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query"},
        404: {"model": ErrorResponse, "description": "No relevant chunks found"},
        503: {"model": ErrorResponse, "description": "LLM or embedding service unavailable"},
        504: {"model": ErrorResponse, "description": "LLM timeout"},
    },
)
async def estimate(
    request: EstimateRequest,
    pipeline: EstimationPipeline = Depends(get_estimation_pipeline),
) -> EstimateResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        return await pipeline.estimate(request)
    except NoRelevantChunksError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503, detail=f"Embedding service unavailable: {e}"
        )
    except GenerationError as e:
        raise HTTPException(
            status_code=503, detail=f"LLM service unavailable: {e}"
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="LLM request timed out")


@router.post(
    "/estimate/validate",
    response_model=ValidateResponse,
    responses={
        503: {"model": ErrorResponse, "description": "LLM or embedding service unavailable"},
        504: {"model": ErrorResponse, "description": "LLM timeout"},
    },
)
async def validate_breakdown(
    request: ValidateRequest,
    pipeline: EstimationPipeline = Depends(get_estimation_pipeline),
) -> ValidateResponse:
    try:
        return await pipeline.validate_breakdown(request)
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503, detail=f"Embedding service unavailable: {e}"
        )
    except GenerationError as e:
        raise HTTPException(
            status_code=503, detail=f"LLM service unavailable: {e}"
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="LLM request timed out")


@router.post(
    "/estimate/batch",
    response_model=BatchEstimateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Services unavailable"},
    },
)
async def estimate_batch(
    request: BatchEstimateRequest,
    pipeline: EstimationPipeline = Depends(get_estimation_pipeline),
) -> BatchEstimateResponse:
    try:
        return await pipeline.estimate_batch(request)
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503, detail=f"Embedding service unavailable: {e}"
        )
    except GenerationError as e:
        raise HTTPException(
            status_code=503, detail=f"LLM service unavailable: {e}"
        )
