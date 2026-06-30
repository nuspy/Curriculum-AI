"""Gestione interventi umani (CAPTCHA/login/2FA/missing data) — piano §9."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..db.enums import InterventionStatus
from ..db.models.browser import Intervention
from ..db.session import get_session


def record_intervention(
    *,
    type: str,
    prompt: str,
    application_id: int | None = None,
    elicitation_id: str | None = None,
) -> int:
    with get_session() as s:
        row = Intervention(
            type=type,
            prompt=prompt,
            application_id=application_id,
            status=InterventionStatus.PENDING.value,
            requested_at=datetime.now(timezone.utc),
            elicitation_id=elicitation_id,
        )
        s.add(row)
        s.flush()
        return row.id


def resolve_intervention(
    intervention_id: int, *, response: dict | None = None, status: str = "resolved"
) -> bool:
    with get_session() as s:
        row = s.get(Intervention, intervention_id)
        if row is None:
            return False
        row.status = status
        row.response = response
        row.resolved_at = datetime.now(timezone.utc)
        return True


def list_pending() -> list[dict]:
    with get_session() as s:
        rows = s.execute(
            select(Intervention).where(Intervention.status == InterventionStatus.PENDING.value)
        ).scalars().all()
        return [
            {"id": r.id, "type": r.type, "prompt": r.prompt, "application_id": r.application_id}
            for r in rows
        ]
