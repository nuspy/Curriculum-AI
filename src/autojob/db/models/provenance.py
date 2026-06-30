from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import TimestampedBase
from ..enums import Provenance


class FieldProvenance(TimestampedBase):
    __tablename__ = "field_provenance"
    __table_args__ = (
        UniqueConstraint("table_name", "row_id", "column_name", name="uq_field_provenance_target"),
    )

    table_name: Mapped[str] = mapped_column(String)
    row_id: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str] = mapped_column(String)
    provenance: Mapped[str] = mapped_column(String, default=Provenance.MISSING.value)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
