from fastapi import APIRouter, status
from fastlimit import rate_limit

from app.config import settings
from app.deps import DB
from app.schemas.link import LinkCreate, LinkDetailOut, LinkListOut, LinkOut
from app.services import link

router = APIRouter(prefix="/api/links", tags=["links"])


def _short_url(slug: str) -> str:
    return f"{settings.BASE_REDIRECT_URL.rstrip('/')}/{slug}"


def _to_out(data: dict) -> LinkOut:
    return LinkOut(short_url=_short_url(data["slug"]), **data)


def _to_detail_out(data: dict) -> LinkDetailOut:
    return LinkDetailOut(short_url=_short_url(data["slug"]), **data)


@router.post(
    "",
    response_model=LinkOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit("10/min")],
)
async def create_link(payload: LinkCreate, db: DB) -> LinkOut:
    data = await link.create_link(db, payload)
    return _to_out(data)


@router.get("", response_model=LinkListOut)
async def list_links(db: DB) -> LinkListOut:
    data = await link.list_links(db)
    out = [_to_out(item) for item in data]
    return LinkListOut(links=out, count=len(out))


@router.get("/{slug}", response_model=LinkDetailOut)
async def get_link(slug: str, db: DB) -> LinkDetailOut:
    data = await link.get_link_detail(db, slug)
    return _to_detail_out(data)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(slug: str, db: DB) -> None:
    await link.delete_link(db, slug)
