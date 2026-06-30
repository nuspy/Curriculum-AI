from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase


class ApprovedAnswer(TimestampedBase):
    __tablename__ = "approved_answers"

    question_norm: Mapped[str] = mapped_column(String, index=True)
    question_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    profile_field_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoverLetterTemplate(TimestampedBase):
    __tablename__ = "cover_letter_templates"

    name: Mapped[str] = mapped_column(String)
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    tone: Mapped[str | None] = mapped_column(String, nullable=True)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    placeholders: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
