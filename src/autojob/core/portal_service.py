"""Registro portali: seed YAML→DB, filtri per policy/rischio, costruzione URL ricerca."""

from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import select

from ..config.loader import load_portals_seed
from ..db.models.portals import Portal
from ..db.session import get_session

_RISK_RANK = {"low": 0, "med": 1, "high": 2, "extreme": 3}
_SEED_COLS = (
    "name", "base_url", "adapter_key", "search_url_template",
    "automation_policy", "requires_account", "tos_risk", "enabled",
)


def _portal_dict(p: Portal) -> dict:
    return {
        "id": p.id, "name": p.name, "slug": p.slug, "base_url": p.base_url,
        "adapter_key": p.adapter_key, "search_url_template": p.search_url_template,
        "automation_policy": p.automation_policy, "requires_account": p.requires_account,
        "tos_risk": p.tos_risk, "enabled": p.enabled,
    }


def seed_portals(*, overwrite: bool = False) -> dict:
    seed = load_portals_seed()
    seeded = 0
    with get_session() as s:
        for row in seed:
            slug = row.get("slug")
            if not slug:
                continue
            existing = s.execute(select(Portal).where(Portal.slug == slug)).scalar_one_or_none()
            if existing and not overwrite:
                continue
            p = existing or Portal(slug=slug)
            for k in _SEED_COLS:
                if k in row:
                    setattr(p, k, row[k])
            if existing is None:
                s.add(p)
            seeded += 1
    return {"seeded": seeded, "total_in_seed": len(seed)}


def get_portal(slug: str) -> dict | None:
    with get_session() as s:
        p = s.execute(select(Portal).where(Portal.slug == slug)).scalar_one_or_none()
        return _portal_dict(p) if p else None


def list_portals(criteria: dict | None = None) -> list[dict]:
    criteria = criteria or {}
    with get_session() as s:
        rows = s.execute(select(Portal).where(Portal.enabled.is_(True))).scalars().all()
    out = [_portal_dict(p) for p in rows]

    max_risk = criteria.get("max_tos_risk")
    if max_risk:
        cap = _RISK_RANK.get(max_risk, 3)
        out = [p for p in out if _RISK_RANK.get(p["tos_risk"], 3) <= cap]
    if criteria.get("searchable_only"):
        out = [p for p in out if p["search_url_template"]]
    if criteria.get("no_account"):
        out = [p for p in out if not p["requires_account"]]
    if criteria.get("exclude_read_only", True):
        out = [p for p in out if p["automation_policy"] != "read_only"]
    return out


def build_search_url(portal: dict, criteria: dict) -> str | None:
    tmpl = portal.get("search_url_template") or ""
    if not tmpl:
        return None
    kw = criteria.get("keywords") or criteria.get("query") or ""
    if isinstance(kw, (list, tuple)):
        kw = " ".join(map(str, kw))
    loc = criteria.get("location") or ""
    try:
        return tmpl.format(keywords=quote_plus(str(kw)), location=quote_plus(str(loc)))
    except Exception:
        return tmpl
