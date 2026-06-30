from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import __version__

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "autojob", "version": __version__}


@router.get("/ready")
async def ready(request: Request):
    st = getattr(request.app.state, "status", {}) or {}
    critical_ok = bool(st.get("db_ok")) and bool(st.get("vec"))
    payload = {
        "ready": critical_ok and bool(st.get("schema_ready")),
        "components": {
            "db": "ok" if st.get("db_ok") else "fail",
            "sqlite_vec": st.get("vec") or "fail",
            "schema": "ok" if st.get("schema_ready") else "not_initialized",
            "browser_driver": st.get("driver"),
            "llm": "not_checked",  # preflight in Fase 1
        },
        "errors": st.get("errors", []),
        "version": __version__,
    }
    return JSONResponse(payload, status_code=200 if critical_ok else 503)


@router.post("/admin/shutdown")
async def admin_shutdown():
    """Spegne LM Studio (ciò che il daemon ha avviato) e arresta il daemon."""
    from ..core.lmstudio import manager
    from .activity import trigger_shutdown

    res = await manager.shutdown()
    trigger_shutdown()
    return {"ok": True, "lmstudio": res}
