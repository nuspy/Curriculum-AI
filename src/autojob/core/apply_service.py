"""Orchestrazione candidatura (piano §9): ciclo read→decide→act→wait→verify, sezioni
ripetute, e invio rispettando le modalità (default manual)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from sqlalchemy import select

from ..config.settings import get_settings
from ..db.enums import ApplicationStatus as AS
from ..db.models.applications import Application
from ..db.session import get_session
from . import profile_service
from .application_service import save_application_status
from .audit import log_action
from .browser_session import get_session_driver
from .form_service import analyze_form, map_profile_to_form

_OPEN = (AS.DRAFT.value, AS.IN_PROGRESS.value, AS.NEEDS_USER.value)
_STATUS_MAP = {
    "ready_for_review": AS.IN_PROGRESS.value,
    "needs_user": AS.NEEDS_USER.value,
    "intervention": AS.NEEDS_USER.value,
    "submitted": AS.SUBMITTED.value,
    "submit_failed": AS.FAILED.value,
}


def _ar(r) -> dict:
    return dataclasses.asdict(r)


def _ensure_application(job_id: int) -> int:
    with get_session() as s:
        existing = s.execute(
            select(Application)
            .where(Application.job_posting_id == job_id, Application.status.in_(_OPEN))
            .order_by(Application.id.desc())
        ).scalars().first()
        if existing:
            return existing.id
        a = Application(
            job_posting_id=job_id, status=AS.DRAFT.value, started_at=datetime.now(timezone.utc)
        )
        s.add(a)
        s.flush()
        return a.id


def _update_application(app_id: int, status: str, filled: list, mode: str) -> None:
    with get_session() as s:
        a = s.get(Application, app_id)
        if a is None:
            return
        a.status = _STATUS_MAP.get(status, AS.IN_PROGRESS.value)
        a.mode = mode
        a.field_log = filled
        if status == "submitted" and a.submitted_at is None:
            a.submitted_at = datetime.now(timezone.utc)


def _verify(plans: list[dict], snap) -> list[dict]:
    byname, bylabel = {}, {}
    for e in snap.elements:
        nm = (e.attrs or {}).get("name")
        if nm:
            byname[nm] = e
        if e.label:
            bylabel[e.label] = e
    out = []
    for p in plans:
        if p.get("needs_user") or p.get("action") in (None, "skip"):
            continue
        e = byname.get(p.get("name")) or bylabel.get(p.get("label"))
        ok = False
        if e is not None:
            if p["action"] == "check":
                ok = bool(e.checked) == bool(p["value"])
            elif p["action"] == "upload":
                ok = bool(e.value)
            else:
                ok = (e.value or "") == str(p["value"]) or str(p["value"]) in (e.value or "")
        out.append({"label": p.get("label"), "name": p.get("name"), "ok": ok})
    return out


async def fill_application(job_id: int, *, autosubmit: bool = False, driver=None) -> dict:
    if not job_id:
        return {"ok": False, "reason": "job_id_required"}
    drv = driver or await get_session_driver()
    snap = await drv.get_snapshot()
    fm = analyze_form(snap)
    prof = profile_service.get_profile()
    cv = str(get_settings().cv_path) if get_settings().cv_path else None
    plans = map_profile_to_form(fm, prof, cv_path=cv)
    app_id = _ensure_application(job_id)

    filled, errors = [], []
    needs_user = [p for p in plans if p.get("needs_user")]
    for p in plans:
        if p.get("needs_user") or p.get("action") in (None, "skip"):
            continue
        idx, act = p["index"], p["action"]
        if act == "fill":
            r = await drv.fill(idx, str(p["value"]))
        elif act == "select":
            r = await drv.select_option(idx, value=p.get("value"), label=p.get("label_value"))
        elif act == "check":
            r = await drv.set_checkbox(idx, bool(p["value"]))
        elif act == "upload":
            r = await drv.upload_file(idx, [p["value"]])
        else:
            continue
        log_action(application_id=app_id, tool="fill_application", action_type=act,
                   target_index=idx, params={"source": p.get("source")}, result=_ar(r), success=r.ok)
        (filled if r.ok else errors).append(
            {"index": idx, "label": p.get("label"), "source": p.get("source"),
             "ok": r.ok, "error": r.error_kind}
        )

    await drv.wait_for_dom_change(timeout_ms=1500)
    captcha = await drv.detect_captcha()
    snap2 = await drv.get_snapshot()
    verify = _verify(plans, snap2)

    mode = (prof.get("preferences") or {}).get("submit_mode") or get_settings().submit_mode
    submit_index = fm.get("submit_index")
    submitted = False
    if needs_user:
        status = "needs_user"
    elif captcha:
        status = "intervention"
    else:
        status = "ready_for_review"

    if autosubmit and mode == "auto" and status == "ready_for_review" and submit_index is not None:
        r = await drv.click(submit_index)
        submitted = r.ok
        status = "submitted" if r.ok else "submit_failed"
        log_action(application_id=app_id, tool="submit_application", action_type="click",
                   target_index=submit_index, result=_ar(r), success=r.ok)

    _update_application(app_id, status, filled, mode)
    return {
        "ok": True, "application_id": app_id, "status": status, "mode": mode,
        "filled": filled, "errors": errors,
        "needs_user": [{"label": p.get("label"), "reason": p.get("reason")} for p in needs_user],
        "verify": verify, "captcha": bool(captcha), "submit_index": submit_index,
        "submitted": submitted,
    }


async def add_repeating_section(section_type: str = "", driver=None) -> dict:
    drv = driver or await get_session_driver()
    fm = analyze_form(await drv.get_snapshot())
    if not fm.get("add_indexes"):
        return {"ok": False, "reason": "no_add_button"}

    st = (section_type or "").lower()
    chosen = None
    for b in fm["buttons"]:
        if b["kind"] == "add" and st and st in (b["label"] or "").lower():
            chosen = b["index"]
            break
    if chosen is None:
        chosen = fm["add_indexes"][0]

    before_groups = set(fm["groups"].keys())
    before_fields = fm["field_count"]
    await drv.click(chosen)
    await drv.wait_for_dom_change(timeout_ms=4000)
    fm2 = analyze_form(await drv.get_snapshot())
    new_groups = list(set(fm2["groups"].keys()) - before_groups)
    return {
        "ok": True,
        "clicked_index": chosen,
        "added": fm2["field_count"] > before_fields or bool(new_groups),
        "new_group_ids": new_groups,
        "field_count_before": before_fields,
        "field_count_after": fm2["field_count"],
    }


async def submit_application(
    application_id: int | None = None, *, force: bool = False, driver=None
) -> dict:
    drv = driver or await get_session_driver()
    fm = analyze_form(await drv.get_snapshot())
    si = fm.get("submit_index")
    if si is None:
        return {"ok": False, "reason": "no_submit_button"}
    if await drv.detect_captcha():
        return {"ok": False, "reason": "captcha_present", "status": "intervention"}

    prof = profile_service.get_profile()
    mode = (prof.get("preferences") or {}).get("submit_mode") or get_settings().submit_mode
    if mode == "manual" and not force:
        return {"ok": False, "reason": "manual_mode_requires_confirmation",
                "submit_index": si, "mode": mode}

    r = await drv.click(si)
    if application_id:
        save_application_status(
            application_id, AS.SUBMITTED.value if r.ok else AS.FAILED.value, {"mode": mode}
        )
        log_action(application_id=application_id, tool="submit_application", action_type="click",
                   target_index=si, result=_ar(r), success=r.ok)
    return {"ok": r.ok, "submitted": r.ok, "mode": mode, "submit_index": si}
