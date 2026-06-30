"""Lettura/scrittura del profilo utente e delle preferenze (con provenance)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.enums import Provenance
from ..db.models.preferences import Preferences
from ..db.models.profile import (
    Certification,
    Education,
    Language,
    Project,
    Publication,
    Skill,
    UserProfile,
    WorkExperience,
)
from ..db.provenance import record_provenance
from ..db.session import get_session

_PROFILE_COLUMNS = {
    "full_name", "headline", "email", "phone", "location",
    "work_auth", "default_language", "links", "summary",
}

_SUBENTITIES = {
    "work_experience": (WorkExperience, WorkExperience.order_index),
    "education": (Education, Education.order_index),
    "skills": (Skill, Skill.id),
    "languages": (Language, Language.id),
    "certifications": (Certification, Certification.id),
    "projects": (Project, Project.id),
    "publications": (Publication, Publication.id),
}


def _row_to_dict(obj, exclude: tuple = ()) -> dict:
    out: dict = {}
    for col in obj.__table__.columns:
        if col.name in exclude:
            continue
        val = getattr(obj, col.name)
        out[col.name] = val.isoformat() if isinstance(val, datetime) else val
    return out


def get_or_create_profile(session: Session) -> UserProfile:
    p = session.execute(
        select(UserProfile).order_by(UserProfile.id).limit(1)
    ).scalar_one_or_none()
    if p is None:
        p = UserProfile(default_language="en")
        session.add(p)
        session.flush()
    return p


def get_profile(sections: list[str] | None = None) -> dict:
    wants = set(sections) if sections else None

    def inc(name: str) -> bool:
        return wants is None or name in wants

    with get_session() as s:
        p = get_or_create_profile(s)
        data: dict = {"profile": _row_to_dict(p)}
        for name, (model, order_col) in _SUBENTITIES.items():
            if inc(name):
                rows = s.execute(
                    select(model).where(model.profile_id == p.id).order_by(order_col)
                ).scalars().all()
                data[name] = [_row_to_dict(r) for r in rows]
        if inc("preferences"):
            pref = s.execute(
                select(Preferences).where(Preferences.profile_id == p.id).limit(1)
            ).scalar_one_or_none()
            data["preferences"] = _row_to_dict(pref) if pref else None
        return data


def update_profile(patch: dict, source: str = "declared") -> dict:
    """Aggiorna i campi anagrafici del profilo e registra la provenance per ciascuno."""
    prov = source if source in {p.value for p in Provenance} else Provenance.DECLARED.value
    with get_session() as s:
        p = get_or_create_profile(s)
        applied: list[str] = []
        ignored: list[str] = []
        for k, v in (patch or {}).items():
            if k in _PROFILE_COLUMNS:
                setattr(p, k, v)
                record_provenance(
                    s, table_name="user_profile", row_id=p.id, column_name=k, provenance=prov
                )
                applied.append(k)
            else:
                ignored.append(k)
        s.flush()
        return {"profile_id": p.id, "updated": applied, "ignored": ignored}


def update_preferences(patch: dict) -> dict:
    with get_session() as s:
        p = get_or_create_profile(s)
        pref = s.execute(
            select(Preferences).where(Preferences.profile_id == p.id).limit(1)
        ).scalar_one_or_none()
        if pref is None:
            pref = Preferences(profile_id=p.id)
            s.add(pref)
            s.flush()
        cols = {c.name for c in Preferences.__table__.columns}
        applied = []
        for k, v in (patch or {}).items():
            if k in cols and k not in {"id", "profile_id", "created_at", "updated_at"}:
                setattr(pref, k, v)
                applied.append(k)
        s.flush()
        return {"preferences_id": pref.id, "updated": applied}


def get_profile_provenance() -> dict:
    """Mappa {colonna: provenance} per la riga del profilo (per il cockpit)."""
    from ..db.models.provenance import FieldProvenance

    with get_session() as s:
        p = get_or_create_profile(s)
        rows = s.execute(
            select(FieldProvenance).where(
                FieldProvenance.table_name == "user_profile",
                FieldProvenance.row_id == p.id,
            )
        ).scalars().all()
        return {r.column_name: r.provenance for r in rows}
