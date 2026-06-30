# AutoJob — guida per Claude Code

Sistema **locale e modulare** per cercare, valutare e compilare candidature di lavoro,
pilotato da un agente AI via **MCP**. Tutto locale; nessun servizio commerciale di
scraping/parsing/ranking.

## Architettura (regola d'oro)
Un **daemon** (FastAPI) è l'unica fonte di verità ed espone 4 superfici:
- **MCP** Streamable HTTP su `/mcp/` (per l'agente; vedi `.mcp.json`)
- **WebSocket** `/ext` (estensione MV3, Fase 5)
- **Dashboard cockpit** HTMX su `/` (+ `/ui/*`, `/api/*`)
- **Health/admin**: `/health`, `/ready`, `POST /admin/shutdown`

Stratificazione (NON violarla):
- `core/*_service.py` = logica testabile, **niente import MCP/HTTP**.
- `mcp/server.py` = tool sottili (`@mcp.tool`) che chiamano `core/`. Stesso pattern di AI-rchicad.
- `daemon/dashboard.py` = cockpit che riusa **gli stessi** `core/` (nessuna logica duplicata).
- Controllo browser dietro la porta `browser/port.py:BrowserDriver`; impl: `fake` | `playwright` | `extension`, intercambiabili senza cambiare i tool. Le pagine sono **snapshot indicizzati**: si agisce per `index`, mai per selettore CSS.

## Layout
```
src/autojob/
  daemon/   app · lifespan · health · dashboard · ws_bridge · ext_hub · ext_token · activity · mcp_mount · run
  mcp/      server.py (37 tool)
  core/     profile, cv_ingest, extract, ranking, generation, form, apply, application,
            portal, search, answer_cache, audit, intervention, browser_session, lmstudio
  browser/  port · snapshot · snapshot_js · registry · drivers/{fake,playwright,extension}_driver
  llm/      client (chat) · embeddings · (LM Studio/Ollama OpenAI-compatible)
  db/       base · session (sqlite-vec hook) · enums · schema (vec_ddl) · models/*
  config/   settings (pydantic-settings AUTOJOB_*) · loader
  dashboard/templates/*.html (HTMX)
alembic/    0001_init · 0002_vectors
extension/  MV3 (manifest, src/background.js, snapshot.js, page_actions.js, options/sidepanel/popup)
config/     default.toml (riferimento) · portals.seed.yaml
tests/      pytest (marker `browser` per i test chromium reali)
```

## Eseguire
```bash
uv sync
uv run alembic upgrade head        # crea DB SQLite + tabelle vec0
uv run autojobd                    # daemon su 127.0.0.1:8765  (oppure: uv run autojob up)
uv run pytest                      # tutti i test (uv run pytest -m "not browser" = senza chromium)
uv run ruff check src tests
```
Cockpit: `http://127.0.0.1:8765/` · MCP: `http://127.0.0.1:8765/mcp/` · spegnimento: `uv run autojob down`.

## Browser driver
- `fake` (default, test).
- `playwright`: `AUTOJOB_BROWSER_DRIVER=playwright`; sessione reale loggata con `AUTOJOB_CDP_URL=http://127.0.0.1:9222` (avvia Chrome con `--remote-debugging-port=9222`), altrimenti lancia un chromium.
- `extension`: `AUTOJOB_BROWSER_DRIVER=extension` + carica `extension/` unpacked e incolla il token (`data/ext_token`) nelle opzioni.

## LLM / embeddings
Provider locale OpenAI-compatible (LM Studio `:1234`, Ollama `:11434`). **Lifecycle**: con
`AUTOJOB_LMS_AUTOSTART=1` il daemon avvia LM Studio e carica il modello di default on-demand
(via CLI `lms`) e li **spegne dopo `AUTOJOB_IDLE_SHUTDOWN_MINUTES` (30) di inattività**. Embeddings
multilingue consigliato **bge-m3** (1024-d). Se l'LLM non è raggiungibile i tool degradano
(`llm_unavailable`/semantico saltato) invece di crashare.

## Convenzioni / invarianti
- Modelli SQLAlchemy 2.0 tipizzati; enum salvati come **stringa** (`db/enums.py`), niente CHECK.
- **Provenance** per ogni campo profilo/CV (`certain|declared|inferred|missing`); **mai inventare**: i dati mancanti su campi obbligatori → `needs_user` / elicitation.
- **Duplicate-guard** (§memoria candidature): identità annuncio a 3 livelli — `canonical_job_key` (URL norm + external_id), `content_hash`, `fingerprint` (`utils/hashing.py`). `check_application_status` → badge estensione rosso/ambra; reinvio sempre possibile.
- **Modalità invio** `submit_mode` (default **manual**): non si invia mai senza conferma/`force`.
- Ciclo d'azione: read → decide (`map_profile_to_form`) → act → wait → **verify** → log (`action_log`).

## Estendere
- **Nuovo tool MCP**: scrivi la logica in `core/<x>_service.py`, poi un wrapper sottile in `mcp/server.py`.
- **Nuovo portale**: aggiungi a `config/portals.seed.yaml` e `seed_portals`.
- **Migrazione**: `uv run alembic revision --autogenerate -m "..."`; le tabelle vec0 stanno in `0002` via `db/schema.vec_ddl` (riusato anche da `create_all_schema` nei test — niente drift).

## ToS / sicurezza
LinkedIn/Indeed/Glassdoor vietano l'automazione anche nel browser loggato (rischio limitazione
account, accettato dall'utente). Mitigazioni attive: **default manual**, rate-limit + jitter
(`utils/rate_limit.py`), sessione reale, `automation_policy`/`tos_risk` per portale. Niente bypass CAPTCHA: si rileva e si passa a `intervention`.

## Limiti noti
- Il JS dell'estensione non è testato in CI (serve Chrome reale): caricare unpacked.
- `portals.seed.yaml` è letto da `config/` del repo → modalità supportata = **run da sorgente / editable** (uv). Un wheel autonomo dovrebbe impacchettare il seed.
- Warning deprecazione `TestClient`/httpx silenziato in `pyproject` (filterwarnings).
