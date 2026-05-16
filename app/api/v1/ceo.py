"""CEO endpoints — RAG query and daily summary."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.ceo_request import CeoQueryRequest
from app.api.schemas.ceo_response import CeoDailySummaryResponse, CeoQueryResponse
from app.core.generation import GenerationError
from app.dependencies import get_ceo_service
from app.services.ceo_service import CeoService

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/ceo")


@router.post(
    "/query",
    response_model=CeoQueryResponse,
    summary="CEO RAG query",
)
async def ceo_query(
    body: CeoQueryRequest,
    service: CeoService = Depends(get_ceo_service),
) -> CeoQueryResponse:
    """Answer a natural-language question from the CEO using RAG over check-in chunks.

    Returns a synthesised answer (~80 words), a confidence level, and up to 5 source
    excerpts with their employee name and date.

    Raises:
        503: If the generation service (Gemini) fails.
    """
    try:
        result = await service.query(body.question)
    except GenerationError as exc:
        logger.exception("ceo_query_generation_error", question=body.question[:80])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CeoQueryResponse(**result)


@router.get(
    "/summary",
    response_model=CeoDailySummaryResponse,
    summary="CEO daily executive summary",
)
async def ceo_summary(
    service: CeoService = Depends(get_ceo_service),
) -> CeoDailySummaryResponse:
    """Generate an executive summary of today's completed employee check-ins.

    Returns a ~120-word summary, the count of check-ins included, and the period.

    Raises:
        503: If the generation service (Gemini) fails.
    """
    try:
        result = await service.daily_summary()
    except GenerationError as exc:
        logger.exception("ceo_summary_generation_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CeoDailySummaryResponse(**result)
