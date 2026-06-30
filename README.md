# AutoJob

Sistema **locale e modulare** per cercare, valutare e compilare candidature di lavoro online,
pilotato da un **agente AI pluggable** tramite **MCP**. Tutto locale: niente servizi esterni per
ricerca, parsing CV, ranking, generazione, automazione browser o storage.

## Architettura (sintesi)

Un **daemon locale persistente** (FastAPI/uvicorn) è l'unica fonte di verità ed espone:
- **MCP** via Streamable HTTP (`/mcp`) — per l'agente (Claude Code, modello locale, ecc.);
- **WebSocket** (`/ext`) — per l'estensione browser MV3 (Fase 5);
- **HTTP/API + dashboard** (`/api`, `/`) — per il supervisore umano.

La logica vive in `core/*_service.py` (testabile, niente import MCP/HTTP); i tool MCP sono wrapper
sottili; il controllo browser è dietro la porta `browser.port.BrowserDriver` con implementazioni
intercambiabili (MVP via CDP/claude-in-chrome → estensione custom).

Vedi il piano completo: `~/.claude/plans/voglio-sviluppare-un-sistema-tingly-cook.md`.

## Sviluppo

Requisiti: Python ≥ 3.10, [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # crea .venv e installa le dipendenze
uv run alembic upgrade head   # crea il DB SQLite (+ tabelle vec0)
uv run autojobd               # avvia il daemon su 127.0.0.1:8765
uv run pytest                 # test
```

Health check: `GET http://127.0.0.1:8765/health` e `/ready`.

## Quickstart end-to-end

```bash
uv sync
uv run alembic upgrade head           # DB SQLite + tabelle vec0
uv run autojobd                       # daemon (cockpit: http://127.0.0.1:8765/ , MCP: /mcp/)
```

1. **Profilo da CV**: dall'agente MCP `parse_cv` → `normalize_cv` (popola profilo con provenance).
   Richiede LM Studio: parte da solo al primo uso (autostart) con il modello di default; serve anche
   un modello **embedding** (es. `bge-m3`) per il matching.
2. **Ricerca + ranking**: `run_search(keywords=..., location=...)` (multi-portale → dedup → ranking),
   oppure incolla un annuncio con `extract_job_posting(pasted_text=...)` poi `rank_job_matches`.
3. **Review nel cockpit**: apri `http://127.0.0.1:8765/` → tab **Match**, autorizza con un click.
4. **Browser reale**: avvia Chrome con `--remote-debugging-port=9222`, imposta
   `AUTOJOB_BROWSER_DRIVER=playwright` e `AUTOJOB_CDP_URL=http://127.0.0.1:9222` (oppure carica
   l'estensione `extension/` e usa `AUTOJOB_BROWSER_DRIVER=extension`).
5. **Candidatura**: naviga alla pagina, `fill_application(job_id)` (in **manual** non invia),
   poi `submit_application(application_id, force=true)` quando confermi.

Il daemon spegne LM Studio e se stesso dopo 30 min di inattività (`autojob down` per farlo subito).

## Test
```bash
uv run pytest                  # tutto (include test con chromium reale)
uv run pytest -m "not browser" # senza chromium (veloce)
```

## Stato

Fasi 0–6 + lifecycle + cockpit **complete e testate** (48 test). Roadmap completa e decisioni nel
piano: `~/.claude/plans/voglio-sviluppare-un-sistema-tingly-cook.md`.

