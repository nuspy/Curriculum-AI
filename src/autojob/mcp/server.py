"""Server MCP "AutoJob" (FastMCP). Tool sottili sopra ``core/*_service.py``.

Pattern come AI-rchicad: nessuna logica qui, solo wrapper. Servito via Streamable HTTP
montato su ``/mcp`` nel daemon (vedi daemon/mcp_mount.py). Generazione: target=local|agent.
"""

from __future__ import annotations

import dataclasses

from fastmcp import Context, FastMCP

from ..config.settings import get_settings
from ..core import (
    application_service,
    apply_service,
    browser_session,
    cv_ingest_service,
    extract_service,
    form_service,
    generation_service,
    intervention_service,
    portal_service,
    profile_service,
    ranking_service,
    search_service,
)


def build_mcp() -> FastMCP:
    mcp = FastMCP("AutoJob")

    # ---------- Profile / CV ----------
    @mcp.tool
    def get_user_profile(sections: list[str] | None = None) -> dict:
        """Profilo utente + sotto-entità CV + preferenze (filtrabile per sezioni)."""
        return profile_service.get_profile(sections)

    @mcp.tool
    def update_user_profile(patch: dict, source: str = "declared") -> dict:
        """Aggiorna campi anagrafici del profilo, registrando la provenance."""
        return profile_service.update_profile(patch, source)

    @mcp.tool
    def update_preferences(patch: dict) -> dict:
        """Aggiorna le preferenze di ricerca/candidatura."""
        return profile_service.update_preferences(patch)

    @mcp.tool
    def parse_cv(path: str | None = None) -> dict:
        """Estrae il testo del CV (PDF/DOCX/HTML/MD). Default: AUTOJOB_CV_PATH."""
        return cv_ingest_service.parse_cv(path)

    @mcp.tool
    async def normalize_cv(
        raw_md: str | None = None, path: str | None = None, review: bool = True
    ) -> dict:
        """Struttura il CV nel profilo (provenance + never-invent). Richiede LLM locale."""
        return await cv_ingest_service.normalize_cv(raw_md, path=path, review=review)

    # ---------- Search / extract ----------
    @mcp.tool
    async def extract_job_posting(
        url: str | None = None,
        pasted_text: str | None = None,
        portal_slug: str | None = None,
    ) -> dict:
        """Estrae un annuncio dal testo incollato (URL→Fase 2), lo salva con dedup e dup-guard."""
        return await extract_service.extract_job_posting(
            url=url, pasted_text=pasted_text, portal_slug=portal_slug
        )

    @mcp.tool
    def seed_portals(overwrite: bool = False) -> dict:
        """Carica/aggiorna il registro portali dal seed YAML."""
        return portal_service.seed_portals(overwrite=overwrite)

    @mcp.tool
    def search_job_portals(
        max_tos_risk: str | None = None, no_account: bool = False, searchable_only: bool = True
    ) -> list[dict]:
        """Elenca i portali abilitati filtrati per rischio ToS / account / ricercabilità."""
        return portal_service.list_portals(
            {"max_tos_risk": max_tos_risk, "no_account": no_account, "searchable_only": searchable_only}
        )

    @mcp.tool
    async def search_jobs_on_portal(
        portal_slug: str, keywords: str, location: str | None = None, max: int = 10
    ) -> dict:
        """Cerca annunci su un portale: naviga la ricerca, estrae i link, apre e salva (con dedup)."""
        return await search_service.search_jobs_on_portal(
            portal_slug, {"keywords": keywords, "location": location}, max=max
        )

    @mcp.tool
    async def run_search(
        keywords: str,
        location: str | None = None,
        portals: list[str] | None = None,
        max_per_portal: int = 10,
    ) -> dict:
        """Ricerca multi-portale end-to-end → deduplica → ranking (top 25)."""
        return await search_service.run_search(
            {"keywords": keywords, "location": location},
            portals=portals,
            max_per_portal=max_per_portal,
        )

    @mcp.tool
    def authorize_match(match_id: int, authorized: bool = True) -> dict:
        """Autorizza/revoca una candidatura (gate prima dell'invio)."""
        return ranking_service.set_match_authorized(match_id, authorized)

    # ---------- Browser (Fase 2: READ) ----------
    @mcp.tool
    async def navigate(url: str, wait: bool = True) -> dict:
        """Naviga il browser all'URL (driver da AUTOJOB_BROWSER_DRIVER: fake|playwright)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.navigate(url, wait=wait))

    @mcp.tool
    async def get_page_snapshot(viewport_only: bool = False) -> dict:
        """Snapshot normalizzato indicizzato della pagina corrente (cache in page_snapshots)."""
        return await browser_session.snapshot(viewport_only=viewport_only)

    @mcp.tool
    async def analyze_form() -> dict:
        """Analizza la pagina corrente in un FormModel (campi, submit, next, add)."""
        drv = await browser_session.get_session_driver()
        return form_service.analyze_form(await drv.get_snapshot())

    @mcp.tool
    async def list_targets() -> list[dict]:
        """Elenca tab/finestre aperti (per intercettare gli 'Apply' che aprono un nuovo tab)."""
        drv = await browser_session.get_session_driver()
        return [dataclasses.asdict(t) for t in await drv.list_targets()]

    @mcp.tool
    async def switch_target(target_id: str) -> dict:
        """Passa al tab/finestra indicato (dopo un handoff 'Apply')."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.switch_target(target_id))

    # ---------- Browser (Fase 3: ACT) ----------
    @mcp.tool
    async def fill_form_field(index: int, value: str) -> dict:
        """Compila un campo per indice (CDP isTrusted)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.fill(index, value))

    @mcp.tool
    async def click_element(index: int, expect_new_target: bool = False) -> dict:
        """Clicca un elemento per indice; expect_new_target intercetta nuovi tab (Apply)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.click(index, expect_new_target=expect_new_target))

    @mcp.tool
    async def select_option(index: int, value: str | None = None, label: str | None = None) -> dict:
        """Seleziona un'opzione di una select per indice."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.select_option(index, value=value, label=label))

    @mcp.tool
    async def set_checkbox(index: int, checked: bool = True) -> dict:
        """Imposta una checkbox per indice."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.set_checkbox(index, checked))

    @mcp.tool
    async def upload_file(index: int, paths: list[str]) -> dict:
        """Carica file (es. CV) nell'input per indice (CDP setInputFiles)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.upload_file(index, paths))

    @mcp.tool
    async def scroll(to_index: int | None = None, dy: int = 0, dx: int = 0) -> dict:
        """Scorre la pagina (a un elemento o di dx/dy)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(await drv.scroll(to_index=to_index, dy=dy, dx=dx))

    @mcp.tool
    async def wait_for_dom_change(timeout_ms: int = 8000, expect_url_change: bool = False) -> dict:
        """Attende un cambiamento del DOM/URL (dopo un'azione)."""
        drv = await browser_session.get_session_driver()
        return dataclasses.asdict(
            await drv.wait_for_dom_change(timeout_ms=timeout_ms, expect_url_change=expect_url_change)
        )

    @mcp.tool
    async def verify_field(index: int, expected: str) -> dict:
        """Verifica il valore corrente di un campo (re-snapshot per indice)."""
        drv = await browser_session.get_session_driver()
        el = (await drv.get_snapshot()).by_index(index)
        actual = el.value if el else None
        return {"ok": el is not None and (actual or "") == expected,
                "index": index, "actual": actual, "expected": expected}

    @mcp.tool
    async def detect_captcha() -> dict:
        """Rileva un gate anti-bot (CAPTCHA) nella pagina corrente."""
        drv = await browser_session.get_session_driver()
        cap = await drv.detect_captcha()
        return dataclasses.asdict(cap) if cap else {"present": False}

    @mcp.tool
    async def map_profile_to_form() -> list[dict]:
        """Mappa i campi della pagina corrente ai dati del profilo (FieldPlan)."""
        drv = await browser_session.get_session_driver()
        fm = form_service.analyze_form(await drv.get_snapshot())
        cv = str(get_settings().cv_path) if get_settings().cv_path else None
        return form_service.map_profile_to_form(fm, profile_service.get_profile(), cv_path=cv)

    @mcp.tool
    async def fill_application(job_id: int, autosubmit: bool = False) -> dict:
        """Ciclo d'azione completo: legge form, mappa profilo, compila e verifica.
        Non invia in modalità manual (default); rileva CAPTCHA e dati mancanti."""
        return await apply_service.fill_application(job_id, autosubmit=autosubmit)

    @mcp.tool
    async def autofill_active_form() -> dict:
        """Compila il form della pagina attiva col profilo, senza job_id (un click). Non invia."""
        return await apply_service.autofill_active_form()

    @mcp.tool
    async def prepare_applications(urls: list[str], reapply: bool = False) -> dict:
        """Apre ogni annuncio in una scheda e ne compila il form (NON invia).
        Salta i già-candidati (duplicate-guard) salvo reapply=True. Passa URL già filtrati."""
        return await apply_service.prepare_applications(urls, reapply=reapply)

    @mcp.tool
    async def add_repeating_section(section_type: str = "") -> dict:
        """Aggiunge una sezione ripetuta ('Add experience/education/language') e verifica."""
        return await apply_service.add_repeating_section(section_type)

    @mcp.tool
    async def submit_application(application_id: int | None = None, force: bool = False) -> dict:
        """Invia la candidatura rispettando submit_mode (manual richiede force=True)."""
        return await apply_service.submit_application(application_id, force=force)

    @mcp.tool
    async def request_user_intervention(reason: str, kind: str = "ambiguous", ctx: Context = None) -> dict:
        """Pausa per intervento umano (CAPTCHA/login/dato mancante) via elicitation MCP."""
        iid = intervention_service.record_intervention(type=kind, prompt=reason)
        if ctx is not None:
            try:
                res = await ctx.elicit(reason, response_type=str)
                action = getattr(res, "action", None)
                if action == "accept":
                    data = getattr(res, "data", None)
                    intervention_service.resolve_intervention(iid, response={"text": data})
                    return {"resolved": True, "intervention_id": iid, "response": data}
                return {"resolved": False, "intervention_id": iid, "action": action}
            except Exception as e:  # noqa: BLE001
                return {"resolved": False, "intervention_id": iid, "elicit_error": str(e)[:200]}
        return {"resolved": False, "intervention_id": iid, "pending": True}

    # ---------- Ranking ----------
    @mcp.tool
    async def rank_job_matches(
        job_ids: list[int] | None = None, search_run_id: int | None = None
    ) -> list[dict]:
        """Ranking 0-100 con breakdown, reasons, penalità e probabilità di successo."""
        return await ranking_service.rank_jobs(job_ids, search_run_id)

    @mcp.tool
    def list_job_matches(
        status: str | None = None, min_score: float = 0, limit: int = 50
    ) -> list[dict]:
        """Elenca i match ordinati per punteggio."""
        return ranking_service.list_job_matches(status, min_score, limit)

    @mcp.tool
    async def generate_application_strategy(job_id: int, target: str = "local") -> dict:
        """Strategia di candidatura per-annuncio (JSON)."""
        return await generation_service.generate_application_strategy(job_id, target=target)

    # ---------- Generation ----------
    @mcp.tool
    async def generate_cover_letter(
        job_id: int,
        template: str | None = None,
        tone: str | None = None,
        target: str = "local",
    ) -> dict:
        """Cover letter personalizzata. target=local (LLM locale) | agent (delega prompt)."""
        return await generation_service.generate_cover_letter(
            job_id, template=template, tone=tone, target=target
        )

    @mcp.tool
    async def generate_form_answer(
        question: str, job_id: int, max_len: int | None = None, target: str = "local"
    ) -> dict:
        """Risposta a domanda aperta: prima la cache approved_answers, poi LLM (never-invent)."""
        return await generation_service.generate_form_answer(
            question, job_id, max_len=max_len, target=target
        )

    # ---------- State / duplicate-guard ----------
    @mcp.tool
    def check_application_status(job_identity: dict) -> dict:
        """Duplicate-guard: {state:none|prepared|submitted, strength:strong|fuzzy, details}."""
        return application_service.check_application_status(job_identity)

    @mcp.tool
    def save_application_status(
        application_id: int, status: str, fields: dict | None = None
    ) -> dict:
        """Aggiorna lo stato di una candidatura (submitted imposta submitted_at)."""
        return application_service.save_application_status(application_id, status, fields)

    return mcp
