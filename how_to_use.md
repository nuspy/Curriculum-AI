# AutoJob — Manuale d'uso (how_to_use)

AutoJob cerca, valuta e compila **candidature di lavoro in locale**, pilotato da un agente AI via
**MCP**. Tutto è locale; l'**invio è manuale di default** (niente invii senza tua conferma).

---

## 1. Installazione
Vedi **AGENT_INSTALL.md**. In breve, dalla cartella del repo:
```
python install.py
```
Installa dipendenze, browser (chromium), DB, skill globale `/autojob`, registra l'MCP e avvia il daemon.

## 2. Avvio & spegnimento
```
uv run autojob up      # avvia il daemon se non attivo (idempotente)
uv run autojob down    # spegne daemon + LM Studio (avviati da AutoJob)
uv run autojob info    # mostra configurazione e percorsi
```
- **Cockpit**: http://127.0.0.1:8765/
- **MCP**: http://127.0.0.1:8765/mcp/  (server `autojob`, già in `.mcp.json`)
- Il daemon si **spegne da solo dopo 30 minuti** di inattività.

## 3. Due modi d'uso
### A) Con l'agente (consigliato)
Comandi rapidi: `/autojob` (panoramica) · `/autojob-search <parole> [città]` · `/autojob-apply <match|url>`
· `/autojob-status`. Oppure parla naturalmente ("cerca AI Architect remoto Europa e fai il ranking"):
l'agente usa la skill `autojob` e i tool MCP.

### B) Dal cockpit (review umana)
Apri http://127.0.0.1:8765/ → tab **Match** (autorizza con un click), **Profilo** (campi + provenance),
**Interventi** (CAPTCHA/dati mancanti, risolvi), **Candidature** (stato).

## 4. Flusso completo
1. **Profilo dal CV**: `parse_cv` → `normalize_cv` (riempie il profilo con *provenance*; non inventa).
   Integra con `update_user_profile` / `update_preferences` (salario, località, remoto, modalità, tono).
2. **Ricerca + ranking**: `run_search(keywords, location)` (multi-portale → dedup → ranking) oppure
   incolla un annuncio con `extract_job_posting(pasted_text=...)` poi `rank_job_matches`.
3. **Selezione**: autorizza i match scelti (`authorize_match` o checkbox nel cockpit).
4. **Compilazione**: apri la pagina (`navigate`), `fill_application(job_id)` — compila e verifica,
   **senza inviare** in manual. Gestisce sezioni ripetute, dati mancanti (`needs_user`) e CAPTCHA.
5. **Invio**: solo su conferma → `submit_application(application_id, force=true)`.

## 5. Modalità & sicurezza
- `AUTOJOB_SUBMIT_MODE` = `manual` (default, non invia mai senza `force`) · `semi` · `auto`.
- **Memoria candidature / duplicate-guard**: AutoJob ricorda dove hai già fatto domanda
  (`check_application_status`); l'estensione mostra **badge rosso** (match forte) o **ambra** (possibile
  duplicato) sulle posizioni già candidate — puoi comunque reinviare.
- Niente bypass CAPTCHA: rilevato → stato `intervention`, tocca a te.
- ToS: i grandi portali vietano l'automazione anche nel browser loggato → rischio limitazione account.
  Mitigazioni attive: default manual, rate-limit a misura umana, sessione reale.

## 6. Browser
`AUTOJOB_BROWSER_DRIVER`:
- `fake` — nessun browser (sviluppo/test).
- `playwright` — automazione reale; per la **tua sessione loggata** avvia Chrome con
  `--remote-debugging-port=9222` e imposta `AUTOJOB_CDP_URL=http://127.0.0.1:9222`.
- `extension` — carica `extension/` (vedi `extension/README.md`), incolla il token (`data/ext_token`)
  nelle opzioni; usa la tua sessione reale e mostra il **badge duplicate-guard**.

## 7. LM Studio / embeddings
Provider locale OpenAI-compatible su `:1234`. Con `AUTOJOB_LMS_AUTOSTART=1` (default) il daemon avvia
LM Studio e carica il **modello di default** on-demand (CLI `lms`) e li spegne dopo 30m di inattività.
Per il matching CV↔annuncio serve un modello **embedding** (consigliato `bge-m3`, 1024-d). Se l'LLM non
è disponibile i tool degradano (`llm_unavailable`) invece di bloccarsi.

## 8. Configurazione (env `AUTOJOB_*`)
`HOST`/`PORT` · `DB_PATH`/`DATA_DIR` · `CV_PATH` · `LLM_PROVIDER`/`LLM_BASE_URL`/`LLM_MODEL` ·
`EMBED_MODEL`/`EMBED_BASE_URL` · `BROWSER_DRIVER`/`CDP_URL`/`BROWSER_HEADLESS` ·
`SUBMIT_MODE`/`REAPPLY_POLICY` · `LMS_AUTOSTART`/`LMS_MODEL`/`IDLE_SHUTDOWN_MINUTES`. Vedi `.env.example`.

## 9. Tool MCP (riferimento)
- **Profilo/CV**: parse_cv, normalize_cv, get_user_profile, update_user_profile, update_preferences
- **Ricerca/Ranking**: seed_portals, search_job_portals, search_jobs_on_portal, run_search,
  extract_job_posting, rank_job_matches, list_job_matches, generate_application_strategy
- **Browser**: navigate, get_page_snapshot, analyze_form, map_profile_to_form, fill_form_field,
  click_element, select_option, set_checkbox, upload_file, scroll, wait_for_dom_change, verify_field,
  detect_captcha, list_targets, switch_target, add_repeating_section
- **Candidature**: fill_application, submit_application, authorize_match, check_application_status,
  save_application_status, request_user_intervention, export_application_report

## 10. Troubleshooting
- *Tool `autojob` non disponibili*: il daemon non è attivo → `uv run autojob up` (poi riapri la sessione MCP).
- */ready non "ready"*: esegui `uv run alembic upgrade head` (schema) e controlla i log.
- *Generazione/ranking vuoti*: LM Studio spento o senza modello → caricane uno; verifica `:1234` e `bge-m3`.
- *Browser non agisce*: con `playwright` avvia Chrome col debug port; con `extension` controlla token e URL.
- *Candidatura non parte*: in `manual` è voluto → conferma e usa `submit_application(..., force=true)`.
