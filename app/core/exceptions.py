from pathlib import Path

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SlugAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT


class LinkNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class LinkExpiredError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


def _is_browser_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "json" not in accept


def _render_template(name: str, context: dict) -> HTMLResponse:
    template = _jinja_env.get_template(name)
    return HTMLResponse(content=template.render(context), status_code=status.HTTP_404_NOT_FOUND)


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> HTMLResponse | JSONResponse:
        if _is_browser_request(request):
            if isinstance(exc, (LinkNotFoundError, LinkExpiredError)):
                slug = request.url.path.strip("/")
                return _render_template("not-found.html", {"slug": slug, "detail": exc.message})
            return _render_template("not-found.html", {"slug": "", "detail": exc.message})
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid request", "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Last-resort safety net so an unexpected error never surfaces as
        # a raw 500 with internals leaked to the client.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )
