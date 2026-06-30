"""Ingestione CV → profilo strutturato con provenance (piano §8).

Pipeline: file → testo → estrazione LLM (JSON) → validatore "never invent"
(verifica che i valori compaiano nel testo sorgente) → righe DB + field_provenance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import delete

from ..config.settings import get_settings
from ..db.enums import Provenance
from ..db.models.profile import (
    Certification,
    Education,
    Language,
    Project,
    Publication,
    Skill,
    WorkExperience,
)
from ..db.provenance import record_provenance
from ..db.session import get_session
from ..llm.client import LLMMessage, LLMUnavailable, get_llm_client
from ..utils.hashing import normalize_text
from .profile_service import get_or_create_profile

_SYS = (
    "You extract a CV/resume into STRICT JSON. Output ONLY a JSON object, no prose. "
    "Copy values VERBATIM from the CV text. NEVER invent data: if a field is not present, "
    "omit it or set it to null. Dates as written in the CV."
)

_SCHEMA_HINT = """Return JSON with this shape (omit unknown fields):
{
 "personal_info": {"full_name","headline","email","phone","location","work_auth","summary","links":{"linkedin","github","portfolio"}},
 "work_experience": [{"company","title","employment_type","location","start_date","end_date","is_current","description","tech_stack":[]}],
 "education": [{"institution","degree","field","start_date","end_date","grade","location"}],
 "skills": [{"name","category","level"}],
 "languages": [{"language","cefr_level"}],
 "certifications": [{"name","issuer","issued","expires","credential_id","url"}],
 "projects": [{"name","role","description","tech":[],"url"}],
 "publications": [{"title","venue","year","url"}]
}"""

_SUBLISTS = {
    "work_experience": (WorkExperience, ("company", "title", "description")),
    "education": (Education, ("institution", "degree", "field")),
    "skills": (Skill, ("name",)),
    "languages": (Language, ("language",)),
    "certifications": (Certification, ("name", "issuer")),
    "projects": (Project, ("name", "description")),
    "publications": (Publication, ("title", "venue")),
}

_PI_FIELDS = ("full_name", "headline", "email", "phone", "location", "work_auth", "summary", "links")
_REQUIRED_PI = ("full_name", "email", "phone", "location")


def _extract_text(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suf == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if suf == ".docx":
        import docx

        doc = docx.Document(str(path))
        return "\n".join(par.text for par in doc.paragraphs)
    if suf in {".html", ".htm"}:
        import re

        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
        return re.sub(r"<[^>]+>", " ", raw)
    raise ValueError(f"Formato CV non supportato: {suf}")


def parse_cv(path: str | None = None) -> dict:
    s = get_settings()
    chosen = path or (str(s.cv_path) if s.cv_path else None)
    if not chosen:
        raise ValueError("Nessun CV: passa 'path' o imposta AUTOJOB_CV_PATH.")
    p = Path(chosen)
    if not p.exists():
        raise FileNotFoundError(f"CV non trovato: {p}")
    raw = _extract_text(p)
    sha = hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()
    return {"path": str(p), "raw_md": raw, "sha256": sha, "chars": len(raw)}


def _provenance_for(value, raw_norm: str) -> Provenance:
    if value is None or value == "":
        return Provenance.DECLARED
    v = normalize_text(str(value))
    if not v:
        return Provenance.DECLARED
    if v in raw_norm:
        return Provenance.CERTAIN
    toks = [t for t in v.split() if len(t) > 2]
    if toks and sum(1 for t in toks if t in raw_norm) / len(toks) >= 0.7:
        return Provenance.CERTAIN
    return Provenance.INFERRED


def _write_list(s, profile_id, model, items, raw_norm, replace, prov_cols) -> int:
    if items is None:
        return 0
    if replace:
        s.execute(delete(model).where(model.profile_id == profile_id))
        s.flush()
    cols = {c.name for c in model.__table__.columns}
    reserved = {"id", "profile_id", "created_at", "updated_at"}
    n = 0
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        row = model(profile_id=profile_id)
        for k, v in item.items():
            if k in cols and k not in reserved:
                setattr(row, k, v)
        if "order_index" in cols:
            row.order_index = idx
        s.add(row)
        s.flush()
        for col in prov_cols:
            v = getattr(row, col, None)
            if v:
                record_provenance(
                    s, table_name=model.__tablename__, row_id=row.id,
                    column_name=col, provenance=_provenance_for(v, raw_norm),
                )
        n += 1
    return n


def _persist(data: dict, raw_md: str, replace: bool) -> dict:
    raw_norm = normalize_text(raw_md)
    counts: dict[str, int] = {}
    gaps: list[str] = []
    with get_session() as s:
        p = get_or_create_profile(s)
        pi = data.get("personal_info") or {}
        for col in _PI_FIELDS:
            if col in pi and pi[col] not in (None, ""):
                setattr(p, col, pi[col])
                prov = Provenance.INFERRED if col == "links" else _provenance_for(pi[col], raw_norm)
                record_provenance(
                    s, table_name="user_profile", row_id=p.id, column_name=col, provenance=prov
                )
        s.flush()
        for col in _REQUIRED_PI:
            if not getattr(p, col):
                gaps.append(col)
                record_provenance(
                    s, table_name="user_profile", row_id=p.id,
                    column_name=col, provenance=Provenance.MISSING,
                )
        for name, (model, prov_cols) in _SUBLISTS.items():
            counts[name] = _write_list(
                s, p.id, model, data.get(name), raw_norm, replace, prov_cols
            )
    return {"counts": counts, "gaps": gaps}


async def normalize_cv(
    raw_md: str | None = None,
    *,
    path: str | None = None,
    review: bool = True,
    client=None,
    replace: bool = True,
) -> dict:
    if raw_md is None:
        raw_md = parse_cv(path)["raw_md"]
    client = client or get_llm_client()
    messages = [
        LLMMessage("system", _SYS),
        LLMMessage("user", f"{_SCHEMA_HINT}\n\n--- CV TEXT ---\n{raw_md}"),
    ]
    try:
        raw, data = await client.chat_json(messages, temperature=0.0, max_tokens=4000)
    except LLMUnavailable as e:
        return {"ok": False, "reason": "llm_unavailable", "message": str(e), "raw_chars": len(raw_md)}
    if not isinstance(data, dict):
        return {"ok": False, "reason": "parse_failed", "raw_preview": (raw or "")[:500]}
    result = _persist(data, raw_md, replace=replace)
    result["ok"] = True
    result["review"] = review
    return result
