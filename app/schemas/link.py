import re
from datetime import date, datetime, timedelta, timezone

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    PrivateAttr,
    field_validator,
    model_validator,
)

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class LinkCreate(BaseModel):
    _effective_expiry: datetime | None = PrivateAttr(default=None)

    slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=64,
        description="Optional custom slug. Auto-generated if omitted.",
    )
    target_url: HttpUrl = Field(..., description="The URL the short link redirects to.")
    expires_at: datetime | None = Field(
        default=None, description="Absolute expiry timestamp (ISO 8601)."
    )
    expire_after: int | None = Field(
        default=None,
        gt=0,
        description="Relative expiry in seconds from creation.",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug_charset(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug may only contain letters, numbers, hyphens, and underscores"
            )
        return v

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_be_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return v

    @model_validator(mode="after")
    def resolve_effective_expiry(self) -> LinkCreate:
        candidates = []
        if self.expires_at is not None:
            candidates.append(self.expires_at)
        if self.expire_after is not None:
            candidates.append(
                datetime.now(timezone.utc) + timedelta(seconds=self.expire_after)
            )
        self._effective_expiry = min(candidates) if candidates else None
        return self

    @property
    def effective_expiry(self) -> datetime | None:
        return getattr(self, "_effective_expiry", None)


class LinkOut(BaseModel):
    slug: str
    target_url: str
    short_url: str
    click_count: int
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class DailyClickCount(BaseModel):
    date: date
    count: int


class LinkDetailOut(LinkOut):
    clicks_last_24h: int
    clicks_last_7d: int
    unique_visitors: int
    last_clicked_at: datetime | None
    daily_clicks: list[DailyClickCount]


class LinkListOut(BaseModel):
    links: list[LinkOut]
    count: int
