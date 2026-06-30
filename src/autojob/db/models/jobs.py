from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import MatchStatus


class JobPosting(TimestampedBase):
    __tablename__ = "job_postings"

    portal_id: Mapped[int | None] = mapped_column(ForeignKey("portals.id"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Identità / dedup (piano §6)
    apply_url_norm: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    canonical_job_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    # Contenuto
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    company_name_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tech_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    # Riferimento soft alla cache snapshot (no FK: evita cicli su SQLite)
    raw_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedup_of: Mapped[int | None] = mapped_column(ForeignKey("job_postings.id"), nullable=True)


class JobMatch(TimestampedBase):
    __tablename__ = "job_matches"

    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    search_run_id: Mapped[int | None] = mapped_column(ForeignKey("search_runs.id"), nullable=True)
    score_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    penalties: Mapped[list | None] = mapped_column(JSON, nullable=True)
    criticality: Mapped[str | None] = mapped_column(String, nullable=True)
    success_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default=MatchStatus.NEW.value)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
