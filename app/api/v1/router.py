from fastapi import APIRouter

from app.api.v1.ceo import router as ceo_router
from app.api.v1.checkin import router as checkin_router
from app.api.v1.health import router as health_router
from app.api.v1.speech import router as speech_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(speech_router, tags=["speech"])
router.include_router(checkin_router, tags=["checkin"])
router.include_router(ceo_router, tags=["ceo"])
