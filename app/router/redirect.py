from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from starlette import status

from app.deps import DB
from app.services import link
from app.services.click import record_click

router = APIRouter(tags=["redirect"])


@router.get("/{slug}", status_code=status.HTTP_302_FOUND)
async def redirect_to_target(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DB,
) -> RedirectResponse:
    target_url = await link.resolve_redirect_target(db, slug)

    background_tasks.add_task(
        record_click,
        slug=slug,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
