from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import BaseModel

if TYPE_CHECKING:
    from app.models.click import ClickEvent


class Link(BaseModel):
    __tablename__ = "links"

    slug: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    click_events: Mapped[list[ClickEvent]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )
