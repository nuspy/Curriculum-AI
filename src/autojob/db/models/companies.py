from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase


class Company(TimestampedBase):
    __tablename__ = "companies"

    name: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_name: Mapped[str] = mapped_column(String, unique=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    size: Mapped[str | None] = mapped_column(String, nullable=True)
    locations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
