from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import Provenance
from .models.provenance import FieldProvenance


def record_provenance(
    session: Session,
    *,
    table_name: str,
    row_id: int,
    column_name: str,
    provenance: Provenance | str,
    source: str | None = None,
    confidence: float | None = None,
    evidence_ref: str | None = None,
) -> FieldProvenance:
    """Upsert di una riga ``field_provenance`` per (table, row, column).

    Vedi piano §4: ogni scrittura di campo profilo/CV registra la provenienza.
    ``missing`` non deve mai essere inventato → trigger di elicitation prima dell'uso.
    """
    prov = provenance.value if isinstance(provenance, Provenance) else str(provenance)
    rec = session.execute(
        select(FieldProvenance).where(
            FieldProvenance.table_name == table_name,
            FieldProvenance.row_id == row_id,
            FieldProvenance.column_name == column_name,
        )
    ).scalar_one_or_none()
    if rec is None:
        rec = FieldProvenance(table_name=table_name, row_id=row_id, column_name=column_name)
        session.add(rec)
    rec.provenance = prov
    rec.source = source
    rec.confidence = confidence
    rec.evidence_ref = evidence_ref
    return rec
