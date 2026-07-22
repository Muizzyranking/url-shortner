import shortuuid

from app.config import settings


def generate_slug(length: int | None = None) -> str:
    length = length or settings.SLUG_LENGTH
    return shortuuid.ShortUUID().random(length=length)
