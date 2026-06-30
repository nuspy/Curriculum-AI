---
name: autojob
description: Cerca, valuta e compila candidature di lavoro in locale tramite il sistema AutoJob (MCP). Usa quando l'utente vuole trovare offerte, fare ranking di annunci sul proprio CV, generare cover letter/risposte, o compilare/inviare candidature. Richiede il daemon AutoJob attivo.
---

# AutoJob — interfaccia agente

AutoJob è un sistema **locale** (daemon MCP + browser driver + cockpit). Tu (agente) lo piloti
chiamando i **tool MCP** del server `autojob`. Tutto è locale; l'invio è **manuale di default**
(non inviare mai una candidatura senza conferma esplicita dell'utente).

## 0. Prerequisito: daemon attivo
I tool MCP `autojob` rispondono solo se il daemon è in esecuzione. Se le chiamate falliscono o il
server `autojob` non è connesso, avvialo: esegui in shell `uv run autojob up` nella cartella del
progetto (oppure `autojob up` se installato). Poi procedi. LM Studio si avvia da solo al primo uso
LLM e si spegne dopo 30 min di inattività.

## 1. Profilo da CV (una tantum)
- `parse_cv(path=...)` → estrae il testo del CV (default: `AUTOJOB_CV_PATH`).
- `normalize_cv(path=...)` → struttura il profilo con **provenance** (certain/declared/inferred/missing).
- Verifica/integra con `get_user_profile()` e `update_user_profile(patch, source="declared")`.
- `update_preferences(patch)` per salario, località, remoto, **submit_mode** (manual/semi/auto), tono.
- **Mai inventare** dati: se mancano campi obbligatori, chiedili all'utente (non riempire a caso).

## 2. Ricerca e ranking
- `seed_portals()` la prima volta (carica il registro portali).
- `search_job_portals(max_tos_risk=..., no_account=..., searchable_only=true)` per scegliere i portali.
- `run_search(keywords, location, portals=None, max_per_portal=10)` → ricerca multi-portale, dedup,
  ranking. Ritorna i top match con `score_total`, `score_breakdown`, `reasons`, `success_probability`.
- In alternativa, su testo incollato: `extract_job_posting(pasted_text=...)` poi `rank_job_matches()`.
- Mostra i risultati all'utente; usa `list_job_matches(min_score=..., status=...)` per rivederli.

## 3. Selezione (gate) e candidatura
- L'utente sceglie quali candidature autorizzare: `authorize_match(match_id, authorized=true)`
  (oppure dal **cockpit** su http://127.0.0.1:8765/, tab Match).
- Apri la pagina della candidatura: `navigate(url)` (richiede `AUTOJOB_BROWSER_DRIVER=playwright` o
  `extension`; con driver `fake` non c'è browser reale).
- `analyze_form()` per capire il form; `map_profile_to_form()` per vedere la mappatura.
- `fill_application(job_id)` esegue il **ciclo completo** (compila + verifica). NON invia in `manual`.
  - Se ritorna `needs_user` → mancano dati: chiedili all'utente, aggiorna il profilo, riprova.
  - Se ritorna `captcha`/`intervention` → avvisa l'utente e usa `request_user_intervention(...)`.
- "Add experience/education/…": `add_repeating_section("experience")`.
- **Invio**: solo dopo conferma esplicita dell'utente → `submit_application(application_id, force=true)`.
  In `manual` senza `force` il tool si rifiuta apposta.

## 4. Generazione
- `generate_cover_letter(job_id, target="local")` (o `target="agent"` per farla generare a te).
- `generate_form_answer(question, job_id)` → prima cerca nella cache risposte approvate; se manca un
  dato risponde `needs_user` (non inventare).
- `generate_application_strategy(job_id)`.

## 5. Memoria & duplicati
- `check_application_status(job_identity)` evita reinvii: ritorna `state` (none/prepared/submitted) e
  `strength` (strong/fuzzy). In `extension` l'icona mostra **badge rosso/ambra** sulle posizioni già
  candidate; il reinvio resta possibile previa conferma.
- `save_application_status(application_id, status)` per aggiornare lo stato.

## Tool browser by-index (avanzati)
`get_page_snapshot`, `fill_form_field(index,value)`, `click_element(index)`, `select_option`,
`set_checkbox`, `upload_file(index,paths)`, `scroll`, `wait_for_dom_change`, `verify_field`,
`detect_captcha`, `list_targets`/`switch_target` (handoff multi-tab per gli "Apply" che aprono un tab).

## Regole
- Default **manual**: prepari e verifichi, **non invii** senza conferma.
- Niente bypass CAPTCHA: rileva e passa la palla all'utente.
- Non inventare dati del profilo. Rispetta blacklist e preferenze.
- Volumi a misura umana (rate-limit già attivo) — non martellare i portali.
