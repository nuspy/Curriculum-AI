"""Audit trail: scrittura su action_log (piano §4)."""

from __future__ import annotations

from datetime import datetime, timezone

from ..db.models.browser import ActionLog
from ..db.session import get_session


def log_action(
    *,
    application_id: int | None = None,
    tool: str | None = None,
    action_type: str | None = None,
    target_index: int | None = None,
    target_role: str | None = None,
    params: dict | None = None,
    result: dict | None = None,
    success: bool | None = None,
    snapshot_before_id: int | None = None,
    snapshot_after_id: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    actor: str = "agent",
    session_id: str | None = None,
) -> int:
    with get_session() as s:
        row = ActionLog(
            application_id=application_id,
            session_id=session_id,
            ts=datetime.now(timezone.utc),
            actor=actor,
            tool=tool,
            action_type=action_type,
            target_index=target_index,
            target_role=target_role,
            params=params,
            result=result,
            success=success,
            snapshot_before_id=snapshot_before_id,
            snapshot_after_id=snapshot_after_id,
            latency_ms=latency_ms,
            error=error,
        )
        s.add(row)
        s.flush()
        return row.id
