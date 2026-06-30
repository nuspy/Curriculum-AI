"""Estrazione annuncio (Fase 1: da testo incollato) + upsert con chiavi d'identità."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select

from ..db.models.jobs import JobPosting
from ..db.models.portals import Portal
from ..db.session import get_session
from ..llm.client import LLMMessage, LLMUnavailable, get_llm_client
from .application_service import check_application_status, compute_identity

_JOB_SYS = (
    "Extract a single job posting into STRICT JSON. Output ONLY a JSON object. "
    "Copy values verbatim from the text; use null if unknown. Never invent."
)
_JOB_SCHEMA = """Return JSON (omit unknown):
{"title","company","location","remote_type","employment_type","seniority",
 "salary_min","salary_max","salary_currency","salary_raw",
 "requirements":[],"tech_tags":[],"language","apply_url","external_id"}"""


def _num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d[\d.,]*", str(v))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _heuristic_job(text: str) -> dict:
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return {"title": first[:200] or None}


def upsert_job_posting(fields: dict, *, portal_slug: str | None = None) -> dict:
    title = fields.get("title")
    company = fields.get("company") or fields.get("company_name_raw")
    location = fields.get("location")
    desc = fields.get("description_md")
    url = fields.get("url") or fields.get("apply_url")
    external_id = fields.get("external_id")

    ident = compute_identity(
        url=url, portal_slug=portal_slug, external_id=external_id,
        title=title, company=company, location=location, description=desc,
    )
    # Evita chiavi "costanti" su annunci vuoti
    content_hash = ident["content_hash"] if (title or desc) else None
    canonical = ident["canonical_job_key"] if (url or external_id) else None
    fingerprint = ident["fingerprint"] if (company or title) else None

    with get_session() as s:
        portal_id = None
        if portal_slug:
            portal = s.execute(
                select(Portal).where(Portal.slug == portal_slug)
            ).scalar_one_or_none()
            portal_id = portal.id if portal else None

        existing = None
        if content_hash:
            existing = s.execute(
                select(JobPosting).where(JobPosting.content_hash == content_hash)
            ).scalar_one_or_none()
        if existing is None and canonical:
            existing = s.execute(
                select(JobPosting).where(JobPosting.canonical_job_key == canonical)
            ).scalar_one_or_none()

        row = existing or JobPosting()
        colmap = {
            "title": title,
            "company_name_raw": company,
            "location": location,
            "remote_type": fields.get("remote_type"),
            "employment_type": fields.get("employment_type"),
            "seniority": fields.get("seniority"),
            "salary_min": _num(fields.get("salary_min")),
            "salary_max": _num(fields.get("salary_max")),
            "salary_currency": fields.get("salary_currency"),
            "salary_raw": fields.get("salary_raw"),
            "description_md": desc,
            "requirements": fields.get("requirements"),
            "tech_tags": fields.get("tech_tags"),
            "language": fields.get("language"),
            "url": url,
            "external_id": external_id,
            "portal_id": portal_id,
        }
        for k, v in colmap.items():
            if v is not None:
                setattr(row, k, v)
        row.apply_url_norm = ident["apply_url_norm"]
        row.canonical_job_key = canonical
        row.content_hash = content_hash
        row.fingerprint = fingerprint
        row.captured_at = datetime.now(timezone.utc)
        if existing is None:
            s.add(row)
        s.flush()
        return {
            "ok": True,
            "job_id": row.id,
            "is_new": existing is None,
            "title": row.title,
            "company": row.company_name_raw,
            "identity": {
                "canonical_job_key": canonical,
                "content_hash": content_hash,
                "fingerprint": fingerprint,
            },
        }


async def extract_job_posting(
    url: str | None = None,
    pasted_text: str | None = None,
    *,
    portal_slug: str | None = None,
    client=None,
) -> dict:
    if not pasted_text and url:
        from .browser_session import get_session_driver

        drv = await get_session_driver()
        nav = await drv.navigate(url)
        if not nav.ok:
            return {"ok": False, "reason": "navigation_failed", "message": nav.message}
        pasted_text = await drv.get_page_text()
    if not pasted_text:
        return {"ok": False, "reason": "no_input"}

    client = client or get_llm_client()
    messages = [
        LLMMessage("system", _JOB_SYS),
        LLMMessage("user", f"{_JOB_SCHEMA}\n\n--- JOB POSTING ---\n{pasted_text}"),
    ]
    used = "llm"
    llm_err = None
    try:
        _, data = await client.chat_json(messages, temperature=0.0, max_tokens=2000)
    except LLMUnavailable as e:
        data, llm_err = None, str(e)
    if not isinstance(data, dict):
        data = _heuristic_job(pasted_text)
        used = "heuristic"

    data["description_md"] = data.get("description_md") or pasted_text
    if url:
        data["url"] = url

    res = upsert_job_posting(data, portal_slug=portal_slug)
    res["extraction"] = used
    if llm_err:
        res["llm_error"] = llm_err
    res["applied"] = check_application_status(
        {
            "url": url,
            "portal_slug": portal_slug,
            "external_id": data.get("external_id"),
            "title": data.get("title"),
            "company": data.get("company"),
            "location": data.get("location"),
            "description": data.get("description_md"),
        }
    )
    return res
