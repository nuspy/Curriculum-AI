from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import InterventionStatus


class PageSnapshot(TimestampedBase):
    __tablename__ = "page_snapshots"

    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dom_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    viewport: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    frames: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Riferimento soft (no FK: evita cicli su SQLite)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ActionLog(TimestampedBase):
    __tablename__ = "action_log"

    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    tool: Mapped[str | None] = mapped_column(String, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_role: Mapped[str | None] = mapped_column(String, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Riferimenti soft alle snapshot (no FK: evita cicli)
    snapshot_before_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_after_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Intervention(TimestampedBase):
    __tablename__ = "interventions"

    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default=InterventionStatus.PENDING.value)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    elicitation_id: Mapped[str | None] = mapped_column(String, nullable=True)
