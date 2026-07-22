import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.router import router

STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("urlshortener")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    name=settings.APP_NAME,
    version="1.0.0",
    description="A simple URL shortener API built with FastAPI.",
    lifespan=lifespan,
)


register_exception_handlers(app)
app.include_router(router)
