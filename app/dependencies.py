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
        async with session.begin():
            yield session


def get_embedding_service(
    settings: Settings = Depends(get_settings),
) -> EmbeddingService:
    return EmbeddingService(
        api_key=settings.GEMINI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )


def get_generation_service(
    settings: Settings = Depends(get_settings),
) -> "GenerationService":  # noqa: F821
    from app.core.generation import GenerationService

    return GenerationService(
        api_key=settings.GEMINI_API_KEY,
        model=settings.LLM_MODEL,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
    )


def get_stt_service(
    settings: Settings = Depends(get_settings),
) -> "STTService":  # noqa: F821
    from app.core.speech import STTService

    return STTService(
        project=settings.GOOGLE_CLOUD_PROJECT,
        language_code=settings.STT_LANGUAGE_CODE,
    )


def get_tts_service(
    settings: Settings = Depends(get_settings),
) -> "TTSService":  # noqa: F821
    from app.core.tts import TTSService

    return TTSService(
        language_code=settings.TTS_LANGUAGE_CODE,
        voice_name=settings.TTS_VOICE_NAME,
    )


def get_checkin_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> "CheckInService":  # noqa: F821
    from app.services.checkin_service import CheckInService

    return CheckInService(db=db, embedding_service=embedding_service)


def get_ceo_service(
    db: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    generation_service=Depends(get_generation_service),
) -> "CeoService":  # noqa: F821
    from app.services.ceo_service import CeoService

    return CeoService(
        db=db,
        embedding_service=embedding_service,
        generation_service=generation_service,
    )
