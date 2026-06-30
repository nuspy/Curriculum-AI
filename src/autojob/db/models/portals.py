from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import AutomationPolicy, TosRisk


class Portal(TimestampedBase):
    __tablename__ = "portals"

    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    adapter_key: Mapped[str | None] = mapped_column(String, nullable=True)
    search_url_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_policy: Mapped[str] = mapped_column(String, default=AutomationPolicy.MANUAL.value)
    requires_account: Mapped[bool] = mapped_column(Boolean, default=False)
    tos_risk: Mapped[str] = mapped_column(String, default=TosRisk.MED.value)
    login_state_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
