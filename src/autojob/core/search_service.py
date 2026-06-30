"""Orchestrazione ricerca (piano §ricerca): portali → annunci → ranking, con rate-limit."""

from __future__ import annotations

from ..db.enums import SearchRunStatus
from ..db.models.search import SearchRun
from ..db.session import get_session
from ..utils.rate_limit import RateLimiter
from . import extract_service, portal_service, ranking_service
from .browser_session import get_session_driver

# Rate-limit a misura umana di default (riduce il rischio di rilevamento).
_RATE = RateLimiter(min_interval_s=2.5, jitter_s=1.5)

_JOB_URL_HINTS = (
    "/job", "/jobs", "/vacanc", "/position", "/career", "job-", "/offer",
    "/annunci", "/allas", "/stelle", "/gig", "/opening",
)


def extract_result_links(snapshot, *, limit: int = 50) -> list[str]:
    """Euristica generica: estrae i link agli annunci da una pagina di risultati."""
    seen: set[str] = set()
    out: list[str] = []
    for e in snapshot.elements:
        if e.role != "link" and e.tag != "a":
            continue
        href = (e.attrs or {}).get("href")
        if not href:
            continue
        low = href.lower()
        if not any(h in low for h in _JOB_URL_HINTS):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
        if len(out) >= limit:
            break
    return out


def _create_search_run(criteria: dict, portals) -> int:
    with get_session() as s:
        sr = SearchRun(query=criteria, portals=portals, status=SearchRunStatus.RUNNING.value)
        s.add(sr)
        s.flush()
        return sr.id


def _finish_search_run(sr_id: int, counts: dict) -> None:
    with get_session() as s:
        sr = s.get(SearchRun, sr_id)
        if sr:
            sr.status = SearchRunStatus.DONE.value
            sr.counts = counts


async def search_jobs_on_portal(
    portal_slug: str,
    criteria: dict,
    *,
    max: int = 10,
    driver=None,
    rate: RateLimiter | None = None,
    client=None,
) -> dict:
    portal = portal_service.get_portal(portal_slug)
    if not portal:
        return {"ok": False, "reason": "unknown_portal"}
    if portal["automation_policy"] == "read_only":
        return {"ok": False, "reason": "read_only_portal"}
    url = portal_service.build_search_url(portal, criteria)
    if not url:
        return {"ok": False, "reason": "no_search_url"}

    drv = driver or await get_session_driver()
    rate = rate if rate is not None else _RATE

    await rate.wait(portal_slug)
    nav = await drv.navigate(url)
    if not nav.ok:
        return {"ok": False, "reason": "navigation_failed", "message": nav.message}

    links = extract_result_links(await drv.get_snapshot(), limit=max * 3)
    job_ids: list[int] = []
    results: list[dict] = []
    for link in links[:max]:
        await rate.wait(portal_slug)
        if not (await drv.navigate(link)).ok:
            continue
        text = await drv.get_page_text()
        res = await extract_service.extract_job_posting(
            pasted_text=text, url=link, portal_slug=portal_slug, client=client
        )
        if res.get("ok") and res.get("job_id"):
            job_ids.append(res["job_id"])
            results.append({"url": link, "job_id": res["job_id"], "title": res.get("title")})

    return {
        "ok": True, "portal": portal_slug, "search_url": url,
        "found": len(job_ids), "job_ids": job_ids, "results": results,
    }


async def run_search(
    criteria: dict,
    *,
    portals: list[str] | None = None,
    max_per_portal: int = 10,
    driver=None,
    rate: RateLimiter | None = None,
    client=None,
    emb_client=None,
) -> dict:
    """End-to-end: crea search_run, cerca sui portali, deduplica e fa il ranking."""
    sr_id = _create_search_run(criteria, portals)
    if portals:
        chosen = [p for p in (portal_service.get_portal(s) for s in portals) if p]
    else:
        chosen = portal_service.list_portals({"searchable_only": True})

    drv = driver or await get_session_driver()
    all_ids: list[int] = []
    per_portal: dict[str, object] = {}
    for p in chosen:
        try:
            r = await search_jobs_on_portal(
                p["slug"], criteria, max=max_per_portal, driver=drv, rate=rate, client=client
            )
            ids = r.get("job_ids", []) if r.get("ok") else []
            all_ids += ids
            per_portal[p["slug"]] = r.get("reason") if not r.get("ok") else len(ids)
        except Exception as e:  # noqa: BLE001
            per_portal[p["slug"]] = f"error: {e}"[:120]

    uniq = list(dict.fromkeys(all_ids))
    ranked = (
        await ranking_service.rank_jobs(job_ids=uniq, search_run_id=sr_id, emb_client=emb_client)
        if uniq
        else []
    )
    _finish_search_run(sr_id, {"found": len(uniq), "per_portal": per_portal})
    return {
        "search_run_id": sr_id,
        "portals": [p["slug"] for p in chosen],
        "found": len(uniq),
        "per_portal": per_portal,
        "top": ranked[:25],
    }
