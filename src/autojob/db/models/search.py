from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import SearchRunStatus


class SearchRun(TimestampedBase):
    __tablename__ = "search_runs"

    query: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    portals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default=SearchRunStatus.PENDING.value)
    counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    initiated_by: Mapped[str | None] = mapped_column(String, nullable=True)
