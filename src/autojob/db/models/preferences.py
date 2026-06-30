from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import ReapplyPolicy, RemotePref, SubmitMode


class Preferences(TimestampedBase):
    __tablename__ = "preferences"

    profile_id: Mapped[int | None] = mapped_column(ForeignKey("user_profile.id"), nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String, nullable=True)
    locations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    remote_pref: Mapped[str] = mapped_column(String, default=RemotePref.ANY.value)
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    job_titles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    industries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    seniority_target: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    blacklist_companies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    blacklist_keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    submit_mode: Mapped[str] = mapped_column(String, default=SubmitMode.MANUAL.value)
    reapply_policy: Mapped[str] = mapped_column(String, default=ReapplyPolicy.WARN.value)
    tone: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_apps_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit: Mapped[dict | None] = mapped_column(JSON, nullable=True)
