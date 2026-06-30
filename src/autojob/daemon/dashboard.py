"""Cockpit di review (HTMX) servito dal daemon (piano §6b).

Usa gli stessi ``core/*_service.py`` dei tool MCP: nessuna logica duplicata.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..core import application_service, intervention_service, profile_service, ranking_service

_TPL_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(_TPL_DIR))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "base.html", {})


@router.get("/ui/matches", response_class=HTMLResponse)
async def ui_matches(request: Request, min_score: float = 0):
    matches = ranking_service.list_job_matches(min_score=min_score, limit=100)
    return templates.TemplateResponse(request, "matches.html", {"matches": matches})


@router.post("/api/matches/{match_id}/authorize", response_class=HTMLResponse)
async def authorize(request: Request, match_id: int, authorized: bool = Form(True)):
    ranking_service.set_match_authorized(match_id, authorized)
    matches = ranking_service.list_job_matches(limit=100)
    return templates.TemplateResponse(request, "matches.html", {"matches": matches})


@router.get("/ui/profile", response_class=HTMLResponse)
async def ui_profile(request: Request):
    prof = profile_service.get_profile()
    prov = profile_service.get_profile_provenance()
    return templates.TemplateResponse(request, "profile.html", {"prof": prof, "prov": prov})


@router.get("/ui/interventions", response_class=HTMLResponse)
async def ui_interventions(request: Request):
    return templates.TemplateResponse(
        request, "interventions.html", {"items": intervention_service.list_pending()}
    )


@router.post("/api/interventions/{iid}/resolve", response_class=HTMLResponse)
async def resolve_intervention(request: Request, iid: int):
    intervention_service.resolve_intervention(iid)
    return templates.TemplateResponse(
        request, "interventions.html", {"items": intervention_service.list_pending()}
    )


@router.get("/ui/applications", response_class=HTMLResponse)
async def ui_applications(request: Request):
    return templates.TemplateResponse(
        request, "applications.html", {"apps": application_service.list_applications()}
    )
