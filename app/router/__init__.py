from fastapi import APIRouter

from .health import router as health
from .links import router as links
from .redirect import router as redirect

router = APIRouter()

router.include_router(health)
router.include_router(links)
router.include_router(redirect)
