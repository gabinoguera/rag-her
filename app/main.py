import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.db import close_db, init_db
from app.utils.logging import setup_logging

logger = structlog.stdlib.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)

    init_db(settings)

    await logger.ainfo(
        "Starting HER Conversational Intelligence API",
        version="0.2.0",
        environment=settings.ENVIRONMENT,
        host=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        database_schema=settings.DATABASE_SCHEMA,
        embedding_model=settings.EMBEDDING_MODEL,
        llm_model=settings.LLM_MODEL,
    )
    yield
    await close_db()
    await logger.ainfo("Shutting down HER Conversational Intelligence API")


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="HER — Conversational Intelligence API",
        description="Backend conversacional para check-ins de empleados con análisis semántico vía Gemini.",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    cors_origins = ["http://localhost:3000"] if settings.ENVIRONMENT == "development" else []
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Routers
    application.include_router(v1_router, prefix="/api/v1")

    # Static files — mount last so API routes take priority
    web_dir = os.path.join(os.path.dirname(__file__), "..", "adapters", "primary", "web")
    if os.path.isdir(web_dir):
        from fastapi.staticfiles import StaticFiles

        application.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return application


app = create_app()
