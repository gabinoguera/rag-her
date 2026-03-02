import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas.common import ErrorResponse
from app.api.schemas.quote_generation import GenerateQuoteRequest, GenerateQuoteResponse
from app.core.embeddings import EmbeddingError
from app.core.quote_generation_pipeline import (
    QuoteGenerationError,
    QuoteGenerationPipeline,
)
from app.dependencies import get_quote_generation_pipeline

router = APIRouter()
logger = structlog.stdlib.get_logger()


@router.post(
    "/generate-quote",
    response_model=GenerateQuoteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid transcription"},
        503: {
            "model": ErrorResponse,
            "description": "Reasoning model or embedding service unavailable",
        },
        504: {"model": ErrorResponse, "description": "Reasoning model timeout"},
    },
)
async def generate_quote(
    request: GenerateQuoteRequest,
    pipeline: QuoteGenerationPipeline = Depends(get_quote_generation_pipeline),
) -> GenerateQuoteResponse:
    """Generate a detailed quote from a meeting transcription.

    Uses a 3-step pipeline:
    1. Analyze transcription with reasoning model (o4-mini)
    2. RAG search for similar historical projects
    3. Generate detailed quote with reasoning model
    """
    try:
        return await pipeline.generate(request)
    except QuoteGenerationError as e:
        raise HTTPException(
            status_code=503, detail=f"Quote generation failed: {e}"
        )
    except EmbeddingError as e:
        raise HTTPException(
            status_code=503, detail=f"Embedding service unavailable: {e}"
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail="Reasoning model request timed out"
        )
