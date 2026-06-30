from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import ApplicationStatus


class Application(TimestampedBase):
    __tablename__ = "applications"

    job_match_id: Mapped[int | None] = mapped_column(ForeignKey("job_matches.id"), nullable=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"))
    status: Mapped[str] = mapped_column(String, default=ApplicationStatus.DRAFT.value)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    field_log: Mapped[list | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confirmation_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Reinvio consapevole (override duplicate-guard, piano §6)
    reapply_of: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
