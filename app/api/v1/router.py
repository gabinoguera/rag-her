from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.search import router as search_router
from app.api.v1.stats import router as stats_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(ingest_router, tags=["ingest"])
router.include_router(search_router, tags=["search"])
router.include_router(stats_router, tags=["stats"])
