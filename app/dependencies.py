from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.embeddings import EmbeddingService
from app.db import get_session_factory


async def get_current_settings(
    settings: Settings = Depends(get_settings),
) -> Settings:
    return settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def get_embedding_service(
    settings: Settings = Depends(get_settings),
) -> EmbeddingService:
    return EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )


async def get_ingest_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> "IngestService":  # noqa: F821
    from app.services.ingest_service import IngestService

    return IngestService(db=db, embedding_service=embedding_service)


async def get_retrieval_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    settings: Settings = Depends(get_settings),
) -> "RetrievalService":  # noqa: F821
    from app.core.retrieval import RetrievalService

    return RetrievalService(db=db, embedding_service=embedding_service, settings=settings)


def get_generation_service(
    settings: Settings = Depends(get_settings),
) -> "GenerationService":  # noqa: F821
    from app.core.generation import GenerationService

    return GenerationService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
        timeout=settings.LLM_TIMEOUT,
    )


async def get_estimation_pipeline(
    retrieval_service: "RetrievalService" = Depends(get_retrieval_service),  # noqa: F821
    generation_service: "GenerationService" = Depends(get_generation_service),  # noqa: F821
    settings: Settings = Depends(get_settings),
) -> "EstimationPipeline":  # noqa: F821
    from app.core.pipeline import EstimationPipeline

    return EstimationPipeline(
        retrieval_service=retrieval_service,
        generation_service=generation_service,
        settings=settings,
    )
