from fastapi import APIRouter

from .health import router as health

router = APIRouter()

router.include_router(health)
