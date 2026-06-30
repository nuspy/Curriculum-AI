# Installare AutoJob — istruzioni per un agente

Obiettivo: dato il percorso del repo AutoJob (GitHub o locale), un agente installa e attiva tutto in
automatico. Esegui questi passi in shell.

## Recipe
1. **Ottieni il codice**
   - GitHub: `git clone <repo-url> AutoJob` poi `cd AutoJob`
   - Locale: `cd <percorso-del-repo-AutoJob>`
2. **Installa** (fa tutto: dipendenze, chromium, DB, skill globale, registrazione MCP scope utente, avvio daemon):
   ```
   python install.py
   ```
   Varianti: `--check` (solo verifica) · `--no-daemon` · `--no-browser` · `--mcp-scope project|none`
3. **Verifica**: `http://127.0.0.1:8765/ready` deve rispondere `ready: true`. Cockpit: `http://127.0.0.1:8765/`.
4. **(Opzionale) Installazione nativa come plugin Claude Code**
   ```
   claude plugin marketplace add <percorso-o-repo-AutoJob>
   claude plugin install autojob@autojob-marketplace
   ```

## Requisiti
- `uv` (https://docs.astral.sh/uv/) e Python ≥ 3.10.
- Per le funzioni LLM: LM Studio (CLI `lms`) — si avvia da solo on-demand; serve un modello chat e uno
  di embedding (consigliato `bge-m3`).

## Cosa fa `install.py`
- `uv sync` → installa le dipendenze nel `.venv` del progetto.
- `playwright install chromium` → browser per l'automazione reale (saltabile con `--no-browser`).
- `alembic upgrade head` → crea il DB SQLite + tabelle vettoriali.
- copia la skill in `~/.claude/skills/autojob` → comando `/autojob` disponibile in ogni sessione.
- `claude mcp add --transport http autojob http://127.0.0.1:8765/mcp/ --scope user` (se la CLI
  `claude` è presente); altrimenti l'MCP resta via il `.mcp.json` del progetto.
- `autojob up` → avvia il daemon (cockpit + MCP). LM Studio parte al primo uso LLM; idle-shutdown 30m.

## Dopo l'installazione
- Usa la skill `/autojob` (o i comandi `/autojob-up`, `/autojob-search`, `/autojob-apply`,
  `/autojob-status`). Dettagli operativi in **how_to_use.md** e nella skill `skills/autojob/SKILL.md`.
- Browser reale: avvia Chrome con `--remote-debugging-port=9222` e imposta
  `AUTOJOB_BROWSER_DRIVER=playwright` + `AUTOJOB_CDP_URL=http://127.0.0.1:9222`, oppure carica
  l'estensione `extension/` (token in `data/ext_token`) e usa `AUTOJOB_BROWSER_DRIVER=extension`.
