"""Generazione: cover letter, risposte a domande aperte, strategia (piano §cover).

Ibrido: ``target="local"`` usa il modello locale; ``target="agent"`` restituisce il
prompt composto perché l'agente orchestratore lo completi col proprio modello.
``generate_form_answer`` cerca prima in ``approved_answers`` e non inventa dati mancanti.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..db.models.answers import ApprovedAnswer
from ..db.models.jobs import JobPosting
from ..db.session import get_session
from ..llm.client import LLMMessage, LLMUnavailable, get_llm_client
from ..utils.hashing import normalize_question
from . import profile_service

_COVER_SYS = (
    "You are the candidate's assistant writing a concise, specific cover letter. "
    "Use ONLY facts from the provided profile. Connect the candidate's real experience to the "
    "job's real requirements. No generic filler. Write in the requested language."
)
_ANSWER_SYS = (
    "Answer a job-application question for the candidate using ONLY the provided profile facts. "
    "Be concise and specific. If the answer requires information NOT present in the profile, reply "
    "exactly with 'NEED_USER: <what is missing>' and nothing else. Never invent facts."
)
_STRATEGY_SYS = (
    "You are an application strategist. Output STRICT JSON only: "
    '{"angle","priority","tone","key_points":[],"risks":[],"tailoring":[]}. '
    "Base everything on the provided profile and job."
)


def _profile_brief(prof: dict) -> str:
    p = prof.get("profile") or {}
    skills = ", ".join(s.get("name", "") for s in prof.get("skills", [])[:25])
    exp = "; ".join(
        f"{w.get('title','')} @ {w.get('company','')} ({w.get('start_date','')}-{w.get('end_date','') or 'now'})"
        for w in prof.get("work_experience", [])[:6]
    )
    return (
        f"Name: {p.get('full_name')}\nHeadline: {p.get('headline')}\n"
        f"Location: {p.get('location')}\nSummary: {p.get('summary')}\n"
        f"Skills: {skills}\nExperience: {exp}"
    )


def _job_brief(job: dict) -> str:
    reqs = ", ".join(map(str, job.get("requirements") or []))
    tech = ", ".join(map(str, job.get("tech_tags") or []))
    desc = (job.get("description_md") or "")[:1500]
    return (
        f"Title: {job.get('title')}\nCompany: {job.get('company_name_raw')}\n"
        f"Location: {job.get('location')} | Remote: {job.get('remote_type')}\n"
        f"Seniority: {job.get('seniority')} | Salary: {job.get('salary_raw')}\n"
        f"Tech: {tech}\nRequirements: {reqs}\nDescription: {desc}"
    )


def _locale(job: dict, prof: dict) -> str:
    return job.get("language") or (prof.get("profile") or {}).get("default_language") or "en"


def _load_job_and_profile(job_id: int):
    prof = profile_service.get_profile()
    with get_session() as s:
        j = s.get(JobPosting, job_id)
        if j is None:
            return None, prof
        job = {
            "title": j.title, "company_name_raw": j.company_name_raw, "location": j.location,
            "remote_type": j.remote_type, "seniority": j.seniority, "salary_raw": j.salary_raw,
            "requirements": j.requirements, "tech_tags": j.tech_tags,
            "description_md": j.description_md, "language": j.language, "url": j.url,
        }
    return job, prof


async def generate_cover_letter(
    job_id: int, *, template: str | None = None, tone: str | None = None,
    target: str = "local", client=None,
) -> dict:
    job, prof = _load_job_and_profile(job_id)
    if job is None:
        return {"ok": False, "reason": "job_not_found"}
    locale = _locale(job, prof)
    tmpl_line = f"Template to follow:\n{template}\n" if template else ""
    user = (
        f"Language: {locale}\nTone: {tone or 'professional, warm'}\n"
        f"{tmpl_line}\n"
        f"=== CANDIDATE ===\n{_profile_brief(prof)}\n\n=== JOB ===\n{_job_brief(job)}\n\n"
        "Write the cover letter now."
    )
    if target == "agent":
        return {"ok": True, "mode": "delegate", "system": _COVER_SYS, "prompt": user, "locale": locale}
    client = client or get_llm_client()
    try:
        res = await client.chat(
            [LLMMessage("system", _COVER_SYS), LLMMessage("user", user)],
            temperature=0.4, max_tokens=900,
        )
    except LLMUnavailable as e:
        return {"ok": False, "reason": "llm_unavailable", "message": str(e)}
    return {"ok": True, "mode": "local", "text": res.content.strip(), "locale": locale, "model": res.model}


async def generate_form_answer(
    question: str, job_id: int, *, max_len: int | None = None,
    target: str = "local", client=None,
) -> dict:
    qn = normalize_question(question)
    with get_session() as s:
        cached = s.execute(
            select(ApprovedAnswer)
            .where(ApprovedAnswer.question_norm == qn, ApprovedAnswer.approved.is_(True))
            .limit(1)
        ).scalar_one_or_none()
        if cached and cached.answer:
            cached.usage_count = (cached.usage_count or 0) + 1
            cached.last_used = datetime.now(timezone.utc)
            return {"ok": True, "source": "approved_cache", "answer": cached.answer,
                    "answer_id": cached.id}

    job, prof = _load_job_and_profile(job_id)
    if job is None:
        return {"ok": False, "reason": "job_not_found"}
    limit_txt = f"Max length: ~{max_len} chars.\n" if max_len else ""
    user = (
        f"{limit_txt}Question: {question}\n\n"
        f"=== CANDIDATE ===\n{_profile_brief(prof)}\n\n=== JOB ===\n{_job_brief(job)}"
    )
    if target == "agent":
        return {"ok": True, "mode": "delegate", "system": _ANSWER_SYS, "prompt": user}
    client = client or get_llm_client()
    try:
        res = await client.chat(
            [LLMMessage("system", _ANSWER_SYS), LLMMessage("user", user)],
            temperature=0.3, max_tokens=(min(1200, max_len * 2) if max_len else 600),
        )
    except LLMUnavailable as e:
        return {"ok": False, "reason": "llm_unavailable", "message": str(e)}
    text = res.content.strip()
    if text.upper().startswith("NEED_USER"):
        return {"ok": True, "source": "needs_user", "answer": None, "needs_user": True, "note": text}
    return {"ok": True, "source": "generated", "answer": text, "model": res.model}


async def generate_application_strategy(
    job_id: int, *, target: str = "local", client=None
) -> dict:
    job, prof = _load_job_and_profile(job_id)
    if job is None:
        return {"ok": False, "reason": "job_not_found"}
    user = f"=== CANDIDATE ===\n{_profile_brief(prof)}\n\n=== JOB ===\n{_job_brief(job)}"
    if target == "agent":
        return {"ok": True, "mode": "delegate", "system": _STRATEGY_SYS, "prompt": user}
    client = client or get_llm_client()
    try:
        _, data = await client.chat_json(
            [LLMMessage("system", _STRATEGY_SYS), LLMMessage("user", user)],
            temperature=0.3, max_tokens=800,
        )
    except LLMUnavailable as e:
        return {"ok": False, "reason": "llm_unavailable", "message": str(e)}
    return {"ok": True, "strategy": data if isinstance(data, dict) else {"raw": data}}
