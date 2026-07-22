import json
from datetime import datetime

from app.db.redis import get_redis

CACHE_PREFIX = "link:"
CACHE_TTL_SECONDS = 300

LIST_CACHE_KEY = "links:list"
LIST_CACHE_TTL_SECONDS = 30


async def cache_get_link(slug: str) -> dict | None:
    redis = get_redis()
    raw = await redis.get(f"{CACHE_PREFIX}{slug}")
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set_link(
    slug: str, target_url: str, expires_at: datetime | None
) -> None:
    redis = get_redis()
    payload = json.dumps(
        {
            "target_url": target_url,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
    )
    await redis.set(f"{CACHE_PREFIX}{slug}", payload, ex=CACHE_TTL_SECONDS)


async def cache_invalidate_link(slug: str) -> None:
    redis = get_redis()
    await redis.delete(f"{CACHE_PREFIX}{slug}")
