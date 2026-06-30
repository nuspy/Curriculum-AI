"""Analisi form: da PageSnapshot indicizzato a un FormModel strutturato (piano §9)."""

from __future__ import annotations

from ..browser.snapshot import PageSnapshot

_SUBMIT_WORDS = {"submit", "apply", "send", "candidati", "invia", "finish", "done", "applica"}
_NEXT_WORDS = {"next", "continue", "avanti", "review", "proceed", "prosegui"}
_ADD_WORDS = {"add", "aggiungi", "add another", "+"}

_FIELD_ROLES = {"textbox", "combobox", "checkbox", "radio", "file"}
_FIELD_TAGS = {"input", "select", "textarea"}
_BUTTON_TAGS = {"button"}


def _button_kind(text: str) -> str:
    t = (text or "").strip().lower()
    if any(w in t for w in _SUBMIT_WORDS):
        return "submit"
    if any(w in t for w in _NEXT_WORDS):
        return "next"
    if any(w in t for w in _ADD_WORDS):
        return "add"
    return "button"


def _is_button(e) -> bool:
    return e.role == "button" or e.tag in _BUTTON_TAGS or (e.tag == "input" and (e.type in {"submit", "button"}))


def analyze_form(snapshot: PageSnapshot) -> dict:
    fields: list[dict] = []
    buttons: list[dict] = []
    groups: dict[str, list[int]] = {}

    for e in snapshot.elements:
        gid = e.group_id or "_ungrouped"
        groups.setdefault(gid, []).append(e.index)

        if _is_button(e):
            buttons.append({
                "index": e.index,
                "label": e.text or e.label,
                "kind": _button_kind(e.text or e.label or ""),
            })
        elif e.role in _FIELD_ROLES or e.tag in _FIELD_TAGS:
            fields.append({
                "index": e.index,
                "role": e.role,
                "label": e.label,
                "name": (e.attrs or {}).get("name"),
                "autocomplete": e.autocomplete,
                "type": e.type,
                "required": e.required,
                "group_id": e.group_id,
                "options": e.options,
                "value": e.value,
            })

    submit_index = next((b["index"] for b in buttons if b["kind"] == "submit"), None)
    next_indexes = [b["index"] for b in buttons if b["kind"] == "next"]
    add_indexes = [b["index"] for b in buttons if b["kind"] == "add"]

    return {
        "url": snapshot.url,
        "title": snapshot.title,
        "has_captcha_hint": snapshot.has_captcha_hint,
        "field_count": len(fields),
        "fields": fields,
        "buttons": buttons,
        "submit_index": submit_index,
        "next_indexes": next_indexes,
        "add_indexes": add_indexes,
        "groups": groups,
        "frames": snapshot.frames,
    }


def map_profile_to_form(form_model: dict, profile: dict, *, cv_path: str | None = None) -> list[dict]:
    """Mappa i campi del form ai dati del profilo (step "decide" del ciclo d'azione).

    Ritorna una lista di FieldPlan: {index, name, label, role, required, action, value,
    source, label_value, needs_user, reason}. I dati mancanti su campi obbligatori →
    ``needs_user`` (mai inventati).
    """
    p = profile.get("profile") or {}
    prefs = profile.get("preferences") or {}
    links = p.get("links") if isinstance(p.get("links"), dict) else {}
    plans: list[dict] = []

    for f in form_model.get("fields", []):
        key = " ".join(x for x in [f.get("label"), f.get("name"), f.get("autocomplete")] if x).lower()
        role, ftype, required = f.get("role"), f.get("type"), bool(f.get("required"))
        action = value = source = label_value = None

        if role == "file" or ftype == "file":
            action, value, source = "upload", (cv_path or None), "cv"
        elif any(k in key for k in ("e-mail", "email")):
            action, value, source = "fill", p.get("email"), "profile.email"
        elif "linkedin" in key:
            action, value, source = "fill", links.get("linkedin"), "links.linkedin"
        elif "github" in key:
            action, value, source = "fill", links.get("github"), "links.github"
        elif any(k in key for k in ("portfolio", "website", "sito web")):
            action, value, source = "fill", links.get("portfolio"), "links.portfolio"
        elif any(k in key for k in ("phone", "tel", "telefono", "mobile")):
            action, value, source = "fill", p.get("phone"), "profile.phone"
        elif any(k in key for k in ("location", "city", "country", "città", "citta", "address", "indirizzo")):
            action, value, source = "fill", p.get("location"), "profile.location"
        elif any(k in key for k in ("salary", "retribuzione", "compensation", "stipendio")):
            sal = prefs.get("salary_min")
            action, value, source = "fill", (str(int(sal)) if sal else None), "preferences.salary_min"
        elif role == "checkbox" and any(
            k in key for k in ("agree", "terms", "privacy", "consent", "gdpr", "accetto", "consenso")
        ):
            action, value, source = "check", True, "policy"
        elif ("full name" in key or "fullname" in key or "your name" in key or "nome" in key
              or key.strip() == "name") and "company" not in key and "user" not in key:
            action, value, source = "fill", p.get("full_name"), "profile.full_name"
        elif role == "combobox" and any(k in key for k in ("seniority", "level", "livello")):
            st = prefs.get("seniority_target")
            action, value, source, label_value = "select", st, "preferences.seniority_target", st

        plan = {
            "index": f.get("index"), "name": f.get("name"), "label": f.get("label"),
            "role": role, "required": required, "action": action, "value": value,
            "source": source, "label_value": label_value, "needs_user": False, "reason": None,
        }
        if action is None:
            if required:
                plan.update(needs_user=True, reason="no_mapping")
            else:
                plan["action"] = "skip"
        elif action != "check" and value in (None, ""):
            if required:
                plan.update(needs_user=True, reason=f"missing:{source}", action=None)
            else:
                plan["action"] = "skip"
        plans.append(plan)

    return plans
