import logging

from sqlalchemy import select

from app.db import postgres
from app.models import Link

logger = logging.getLogger("urlshortener.clicks")


async def record_click(
    slug: str,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    from app.models import ClickEvent

    async with postgres.AsyncSessionLocal() as db:
        link = await db.scalar(select(Link).where(Link.slug == slug))
        if link is None:
            logger.info("click recorded for missing slug=%s", slug)
            return

        link.click_count += 1
        db.add(
            ClickEvent(
                link_id=link.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        await db.commit()
