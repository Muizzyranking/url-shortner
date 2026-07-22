from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    cache_get_link,
    cache_invalidate_link,
    cache_set_link,
)
from app.core.exceptions import (
    LinkExpiredError,
    LinkNotFoundError,
    SlugAlreadyExistsError,
)
from app.models import ClickEvent, Link
from app.schemas.link import LinkCreate
from app.utils import generate_slug

MAX_SLUG_GENERATION_ATTEMPTS = 5
DAILY_CLICKS_WINDOW_DAYS = 14


def _serialize_link(link: Link) -> dict:
    return {
        "slug": link.slug,
        "target_url": link.target_url,
        "click_count": link.click_count,
        "created_at": link.created_at.isoformat(),
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


async def create_link(db: AsyncSession, payload: LinkCreate) -> dict:
    if payload.slug:
        existing = await db.scalar(select(Link).where(Link.slug == payload.slug))
        if existing is not None:
            raise SlugAlreadyExistsError(f"slug '{payload.slug}' is already in use")
        slug = payload.slug
    else:
        slug = await _generate_unique_slug(db)

    link = Link(
        slug=slug,
        target_url=str(payload.target_url),
        expires_at=payload.effective_expiry,
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise SlugAlreadyExistsError(f"slug '{slug}' is already in use") from None

    await db.refresh(link)
    return _serialize_link(link)


async def _generate_unique_slug(db: AsyncSession) -> str:
    for _ in range(MAX_SLUG_GENERATION_ATTEMPTS):
        candidate = generate_slug()
        existing = await db.scalar(select(Link).where(Link.slug == candidate))
        if existing is None:
            return candidate
    raise RuntimeError("failed to generate a unique slug after several attempts")


async def list_links(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Link).order_by(Link.created_at.desc()))
    links = list(result.scalars().all())
    data = [_serialize_link(link) for link in links]
    return data


async def get_link_by_slug(db: AsyncSession, slug: str) -> Link:
    link = await db.scalar(select(Link).where(Link.slug == slug))
    if link is None:
        raise LinkNotFoundError(f"no link found for slug '{slug}'")
    return link


async def delete_link(db: AsyncSession, slug: str) -> None:
    link = await get_link_by_slug(db, slug)
    await db.delete(link)
    await db.commit()
    await cache_invalidate_link(slug)


def _is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


async def resolve_redirect_target(db: AsyncSession, slug: str) -> str:
    cached = await cache_get_link(slug)
    if cached is not None:
        expires_at = (
            datetime.fromisoformat(cached["expires_at"])
            if cached["expires_at"]
            else None
        )
        if not _is_expired(expires_at):
            return cached["target_url"]
        await cache_invalidate_link(slug)

    link = await get_link_by_slug(db, slug)
    if _is_expired(link.expires_at):
        raise LinkExpiredError(f"link '{slug}' has expired")

    await cache_set_link(slug, link.target_url, link.expires_at)
    return link.target_url


async def get_link_detail(db: AsyncSession, slug: str) -> dict:
    link = await get_link_by_slug(db, slug)
    now = datetime.now(timezone.utc)

    clicks_last_24h = await db.scalar(
        select(func.count(ClickEvent.id)).where(
            ClickEvent.link_id == link.id,
            ClickEvent.clicked_at >= now - timedelta(hours=24),
        )
    )
    clicks_last_7d = await db.scalar(
        select(func.count(ClickEvent.id)).where(
            ClickEvent.link_id == link.id,
            ClickEvent.clicked_at >= now - timedelta(days=7),
        )
    )
    unique_visitors = await db.scalar(
        select(func.count(func.distinct(ClickEvent.ip_address))).where(
            ClickEvent.link_id == link.id, ClickEvent.ip_address.is_not(None)
        )
    )
    last_clicked_at = await db.scalar(
        select(func.max(ClickEvent.clicked_at)).where(ClickEvent.link_id == link.id)
    )

    today = now.date()
    start_date = today - timedelta(days=DAILY_CLICKS_WINDOW_DAYS - 1)
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    rows = await db.execute(
        select(
            func.date_trunc("day", ClickEvent.clicked_at).label("day"),
            func.count(ClickEvent.id).label("count"),
        )
        .where(ClickEvent.link_id == link.id, ClickEvent.clicked_at >= range_start)
        .group_by("day")
    )
    counts_by_day = {row.day.date(): row.count for row in rows}

    daily_clicks = [
        {
            "date": (start_date + timedelta(days=i)).isoformat(),
            "count": counts_by_day.get(start_date + timedelta(days=i), 0),
        }
        for i in range(DAILY_CLICKS_WINDOW_DAYS)
    ]

    data = _serialize_link(link)
    data["clicks_last_24h"] = clicks_last_24h or 0
    data["clicks_last_7d"] = clicks_last_7d or 0
    data["unique_visitors"] = unique_visitors or 0
    data["last_clicked_at"] = last_clicked_at.isoformat() if last_clicked_at else None
    data["daily_clicks"] = daily_clicks
    return data
