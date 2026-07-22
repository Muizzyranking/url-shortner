from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.cache import ping as redis_ping
from app.deps import DB


class HealthOut(BaseModel):
    status: str
    database: str
    cache: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health(db: DB) -> HealthOut:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    cache_status = "ok" if await redis_ping() else "unreachable"

    overall = "ok" if db_status == "ok" and cache_status == "ok" else "degraded"

    return HealthOut(status=overall, database=db_status, cache=cache_status)
