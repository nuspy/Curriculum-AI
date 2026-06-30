"""Motore di ranking trasparente (piano §7): semantico + regole + penalità.

``score_match`` è una funzione pura (testabile senza LLM/embeddings); ``rank_jobs``
orchestra embeddings + persistenza in ``job_matches``.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select

from ..db.models.jobs import JobMatch, JobPosting
from ..db.session import get_session
from ..llm.embeddings import EmbeddingsUnavailable, cosine, get_embeddings_client
from ..utils.hashing import normalize_text
from . import profile_service

WEIGHTS = {
    "semantic_fit": 0.30,
    "tech_overlap": 0.22,
    "title_role_match": 0.12,
    "seniority_fit": 0.10,
    "salary_fit": 0.10,
    "location_remote_fit": 0.10,
    "recency": 0.06,
}

_JUNIOR = {"junior", "intern", "entry", "graduate", "trainee", "stage"}
_SENIOR = {"senior", "lead", "principal", "staff", "architect", "head"}


def _toks(*values) -> set:
    out: set = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            for item in v:
                out |= set(normalize_text(str(item)).split())
        else:
            out |= set(normalize_text(str(v)).split())
    return {t for t in out if len(t) > 1}


def _days_old(posted: datetime | None, now: datetime) -> float | None:
    if not posted:
        return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return (now - posted).total_seconds() / 86400.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_match(
    job: dict,
    profile: dict,
    prefs: dict,
    *,
    semantic_fit: float,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    prefs = prefs or {}

    job_terms = _toks(job.get("tech_tags"), job.get("requirements"))
    skill_terms = _toks([s.get("name") for s in profile.get("skills", []) if s.get("name")])
    tech_overlap = (len(job_terms & skill_terms) / len(job_terms)) if job_terms else 0.5

    job_title_toks = _toks(job.get("title"))
    pref_titles = prefs.get("job_titles") or []
    if pref_titles and job_title_toks:
        title_role_match = max(
            (len(_toks(t) & job_title_toks) / max(1, len(_toks(t)))) for t in pref_titles
        )
    else:
        title_role_match = 0.5

    job_sen = normalize_text(job.get("seniority"))
    pref_sen = normalize_text(prefs.get("seniority_target"))
    if job_sen and pref_sen:
        seniority_fit = 1.0 if (pref_sen in job_sen or job_sen in pref_sen) else 0.4
    elif not job_sen:
        seniority_fit = 0.6
    else:
        seniority_fit = 0.5

    job_smin = job.get("salary_min")
    pref_smin = prefs.get("salary_min")
    if job_smin and pref_smin:
        salary_fit = 1.0 if job_smin >= pref_smin else max(0.0, float(job_smin) / float(pref_smin))
    elif not job_smin:
        salary_fit = 0.5
    else:
        salary_fit = 0.6

    remote = normalize_text(job.get("remote_type"))
    remote_pref = normalize_text(prefs.get("remote_pref")) or "any"
    loc_terms = _toks(prefs.get("locations"))
    job_loc = _toks(job.get("location"))
    location_remote_fit = 0.4
    if "remote" in remote and remote_pref in {"remote", "any", "hybrid"}:
        location_remote_fit = 1.0
    elif remote_pref == "any":
        location_remote_fit = 0.7
    if loc_terms and (loc_terms & job_loc):
        location_remote_fit = max(location_remote_fit, 0.9)

    days = _days_old(job.get("posted_date"), now)
    if days is None:
        recency = 0.5
    elif days <= 7:
        recency = 1.0
    elif days >= 30:
        recency = 0.0
    else:
        recency = max(0.0, 1.0 - (days - 7) / 23.0)

    comps = {
        "semantic_fit": max(0.0, min(1.0, float(semantic_fit))),
        "tech_overlap": tech_overlap,
        "title_role_match": title_role_match,
        "seniority_fit": seniority_fit,
        "salary_fit": salary_fit,
        "location_remote_fit": location_remote_fit,
        "recency": recency,
    }
    base = 100.0 * sum(WEIGHTS[k] * comps[k] for k in WEIGHTS)

    penalties = []
    desc = job.get("description_md") or ""
    if len(desc) < 200:
        penalties.append({"k": "generic_posting", "d": -8})
    if job_sen in _JUNIOR and pref_sen in _SENIOR:
        penalties.append({"k": "too_junior", "d": -10})
    if job_smin and pref_smin and job_smin < pref_smin:
        penalties.append({"k": "underpaid", "d": -15})
    if not (job.get("company_name_raw") or job.get("company")):
        penalties.append({"k": "unclear_company", "d": -6})
    if days is not None and days > 30:
        penalties.append({"k": "old", "d": -8})
    if job.get("dedup_of"):
        penalties.append({"k": "duplicate", "d": -100})

    total = max(0.0, min(100.0, base + sum(p["d"] for p in penalties)))

    friction = 0.0  # form length / account / open questions: Fase 3+
    success_probability = round(
        _sigmoid(-1.2 + 2.0 * comps["tech_overlap"] + 1.0 * comps["seniority_fit"]
                 + 1.0 * comps["title_role_match"] - 1.5 * friction),
        3,
    )

    reasons = []
    if comps["semantic_fit"] >= 0.6:
        reasons.append("alta affinità semantica CV↔annuncio")
    if comps["tech_overlap"] >= 0.6:
        reasons.append("forte sovrapposizione tecnologica")
    if comps["recency"] >= 0.9:
        reasons.append("annuncio recente")
    if salary_fit >= 1.0 and job_smin:
        reasons.append("salario in linea con le attese")
    if location_remote_fit >= 0.9:
        reasons.append("compatibilità geografica/remoto")
    if not reasons:
        reasons.append("match parziale")

    if recency >= 0.8 and total >= 70:
        criticality = "high"
    elif total >= 50:
        criticality = "medium"
    else:
        criticality = "low"

    return {
        "score_total": round(total, 1),
        "score_breakdown": {k: round(v, 3) for k, v in comps.items()},
        "reasons": reasons,
        "penalties": penalties,
        "criticality": criticality,
        "success_probability": success_probability,
    }


def _job_to_dict(j: JobPosting) -> dict:
    return {
        "id": j.id,
        "title": j.title,
        "company_name_raw": j.company_name_raw,
        "location": j.location,
        "remote_type": j.remote_type,
        "seniority": j.seniority,
        "salary_min": j.salary_min,
        "description_md": j.description_md,
        "tech_tags": j.tech_tags,
        "requirements": j.requirements,
        "posted_date": j.posted_date,
        "dedup_of": j.dedup_of,
    }


def _job_text(jd: dict) -> str:
    parts = [jd.get("title"), jd.get("company_name_raw"), jd.get("location"), jd.get("seniority")]
    parts += [" ".join(map(str, jd.get("tech_tags") or []))]
    parts += [" ".join(map(str, jd.get("requirements") or []))]
    parts += [(jd.get("description_md") or "")[:2000]]
    return "\n".join(p for p in parts if p)


def _profile_text(prof: dict) -> str:
    p = prof.get("profile") or {}
    parts = [p.get("headline"), p.get("summary")]
    parts += [" ".join(s.get("name", "") for s in prof.get("skills", []))]
    parts += [" ".join(w.get("title", "") for w in prof.get("work_experience", []))]
    return "\n".join(x for x in parts if x)


async def rank_jobs(
    job_ids: list[int] | None = None,
    search_run_id: int | None = None,
    *,
    emb_client=None,
) -> list[dict]:
    prof = profile_service.get_profile()
    prefs = prof.get("preferences") or {}
    profile_text = _profile_text(prof)

    with get_session() as s:
        q = select(JobPosting)
        if job_ids:
            q = q.where(JobPosting.id.in_(job_ids))
        job_rows = [(j.id, _job_to_dict(j)) for j in s.execute(q).scalars().all()]

    semantic: dict[int, float] = {}
    emb_status = "ok"
    if job_rows:
        try:
            emb_client = emb_client or get_embeddings_client()
            pvec = await emb_client.embed_one(profile_text) if profile_text else None
            for jid, jd in job_rows:
                jt = _job_text(jd)
                jvec = await emb_client.embed_one(jt) if jt else None
                semantic[jid] = cosine(pvec, jvec) if (pvec and jvec) else 0.0
        except EmbeddingsUnavailable:
            emb_status = "unavailable"
            semantic = {jid: 0.0 for jid, _ in job_rows}

    results: list[dict] = []
    with get_session() as s:
        for jid, jd in job_rows:
            sc = score_match(jd, prof, prefs, semantic_fit=semantic.get(jid, 0.0))
            if emb_status == "unavailable":
                sc["reasons"].append("semantico saltato (embeddings non disponibili)")
            stmt = select(JobMatch).where(JobMatch.job_posting_id == jid)
            stmt = stmt.where(JobMatch.search_run_id == search_run_id) if search_run_id else stmt
            jm = s.execute(stmt).scalars().first()
            if jm is None:
                jm = JobMatch(job_posting_id=jid, search_run_id=search_run_id)
                s.add(jm)
            jm.score_total = sc["score_total"]
            jm.score_breakdown = sc["score_breakdown"]
            jm.reasons = sc["reasons"]
            jm.penalties = sc["penalties"]
            jm.criticality = sc["criticality"]
            jm.success_probability = sc["success_probability"]
            s.flush()
            sc.update({"job_id": jid, "match_id": jm.id,
                       "title": jd.get("title"), "company": jd.get("company_name_raw")})
            results.append(sc)

    results.sort(key=lambda x: x["score_total"], reverse=True)
    return results


def list_job_matches(status: str | None = None, min_score: float = 0, limit: int = 50) -> list[dict]:
    with get_session() as s:
        q = select(JobMatch, JobPosting).join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        if status:
            q = q.where(JobMatch.status == status)
        q = q.where(JobMatch.score_total.isnot(None)).where(JobMatch.score_total >= min_score)
        q = q.order_by(JobMatch.score_total.desc()).limit(limit)
        out = []
        for m, j in s.execute(q).all():
            out.append({
                "match_id": m.id, "job_id": j.id, "title": j.title, "company": j.company_name_raw,
                "score_total": m.score_total, "criticality": m.criticality,
                "success_probability": m.success_probability, "status": m.status,
                "authorized": m.authorized, "reasons": m.reasons, "url": j.url,
            })
        return out


def set_match_authorized(match_id: int, authorized: bool = True) -> dict:
    """Gate prima dell'invio: autorizza/revoca un match (job_matches.authorized)."""
    with get_session() as s:
        m = s.get(JobMatch, match_id)
        if m is None:
            return {"ok": False, "reason": "match_not_found"}
        m.authorized = authorized
        return {"ok": True, "match_id": match_id, "authorized": authorized}
