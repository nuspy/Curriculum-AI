"""Memoria candidature + duplicate-guard (piano §6) e stato candidature."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select

from ..db.enums import ApplicationStatus, AppliedState, MatchStrength
from ..db.models.applications import Application
from ..db.models.jobs import JobPosting
from ..db.session import get_session
from ..utils.hashing import (
    canonical_job_key,
    content_hash,
    job_fingerprint,
    normalize_apply_url,
)

_IDENT_INPUT = ("url", "portal_slug", "external_id", "title", "company", "location", "description")


def compute_identity(
    *,
    url: str | None = None,
    portal_slug: str | None = None,
    external_id: str | None = None,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> dict:
    """Calcola le chiavi d'identità a 3 livelli per un annuncio."""
    return {
        "apply_url_norm": normalize_apply_url(url) if url else None,
        "canonical_job_key": canonical_job_key(
            apply_url=url, portal_slug=portal_slug, external_id=external_id
        ),
        "content_hash": content_hash(
            title=title, company=company, location=location, description=description
        ),
        "fingerprint": job_fingerprint(company, title, location),
    }


def _ensure_identity(job_identity: dict) -> dict:
    ident = dict(job_identity or {})
    if not any(ident.get(k) for k in ("canonical_job_key", "content_hash", "fingerprint")):
        ident.update(compute_identity(**{k: ident.get(k) for k in _IDENT_INPUT}))
    return ident


def check_application_status(job_identity: dict) -> dict:
    """Restituisce {state, strength, details} per il duplicate-guard.

    ``state``: none|prepared|submitted · ``strength``: strong|fuzzy.
    """
    ident = _ensure_identity(job_identity)
    ck, ch, fp = ident.get("canonical_job_key"), ident.get("content_hash"), ident.get("fingerprint")

    none = {"state": AppliedState.NONE.value, "strength": None, "details": None}

    clauses = []
    if ck:
        clauses.append(JobPosting.canonical_job_key == ck)
    if ch:
        clauses.append(JobPosting.content_hash == ch)
    if fp:
        clauses.append(JobPosting.fingerprint == fp)
    if not clauses:
        return none

    with get_session() as s:
        postings = s.execute(select(JobPosting).where(or_(*clauses))).scalars().all()
        if not postings:
            return none
        strong_ids = {
            p.id for p in postings
            if (ck and p.canonical_job_key == ck) or (ch and p.content_hash == ch)
        }
        ids = [p.id for p in postings]
        apps = s.execute(
            select(Application).where(Application.job_posting_id.in_(ids))
        ).scalars().all()
        if not apps:
            return none

        submitted = [a for a in apps if a.status == ApplicationStatus.SUBMITTED.value]
        chosen = submitted[0] if submitted else apps[0]
        state = AppliedState.SUBMITTED.value if submitted else AppliedState.PREPARED.value
        strength = (
            MatchStrength.STRONG.value
            if chosen.job_posting_id in strong_ids
            else MatchStrength.FUZZY.value
        )
        return {
            "state": state,
            "strength": strength,
            "details": {
                "application_id": chosen.id,
                "job_posting_id": chosen.job_posting_id,
                "status": chosen.status,
                "submitted_at": chosen.submitted_at.isoformat() if chosen.submitted_at else None,
            },
        }


def save_application_status(
    application_id: int, status: str, fields: dict | None = None
) -> dict:
    fields = fields or {}
    with get_session() as s:
        app = s.get(Application, application_id)
        if app is None:
            return {"ok": False, "error": "application_not_found"}
        app.status = status
        if status == ApplicationStatus.SUBMITTED.value and app.submitted_at is None:
            app.submitted_at = datetime.now(timezone.utc)
        for k in ("mode", "confirmation_ref", "answers", "files", "field_log",
                  "errors", "screenshots", "reapply_of"):
            if k in fields:
                setattr(app, k, fields[k])
        s.flush()
        return {"ok": True, "application_id": app.id, "status": app.status}


def list_applications(limit: int = 100) -> list[dict]:
    with get_session() as s:
        q = (
            select(Application, JobPosting)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .order_by(Application.id.desc())
            .limit(limit)
        )
        out = []
        for a, j in s.execute(q).all():
            out.append({
                "id": a.id, "status": a.status, "mode": a.mode,
                "job_id": j.id, "title": j.title, "company": j.company_name_raw,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            })
        return out
