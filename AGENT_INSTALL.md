# Installare AutoJob — istruzioni per un agente

Obiettivo: dato il percorso del repo AutoJob (GitHub o locale), un agente installa e attiva tutto in
automatico. Esegui questi passi in shell.

## Recipe
1. **Ottieni il codice**
   - GitHub: `git clone https://github.com/nuspy/Curriculum-AI.git Curriculum-AI` poi `cd Curriculum-AI`
   - Locale: `cd <percorso-del-repo-AutoJob>`
2. **Installa** (fa tutto: dipendenze, chromium, DB, skill globale, registrazione MCP scope utente, avvio daemon):
   ```
   python install.py
   ```
   Varianti: `--check` (solo verifica) · `--no-daemon` · `--no-browser` · `--mcp-scope project|none`
3. **Verifica**: `http://127.0.0.1:8765/ready` deve rispondere `ready: true`. Cockpit: `http://127.0.0.1:8765/`.
4. **(Opzionale) Installazione nativa come plugin Claude Code**
   ```
   claude plugin marketplace add https://github.com/nuspy/Curriculum-AI
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
- Browser reale (Playwright): avvia Chrome con `--remote-debugging-port=9222` e imposta
  `AUTOJOB_BROWSER_DRIVER=playwright` + `AUTOJOB_CDP_URL=http://127.0.0.1:9222`.

## Estensione browser (MV3) — installazione manuale (Chrome non consente l'install da CLI)
`install.py` **non** può caricare automaticamente l'estensione in Chrome, ma a fine installazione
**stampa esattamente cosa fare e da dove** (path assoluto + token). Passi:
1. `chrome://extensions` → attiva **Modalità sviluppatore** → **Carica estensione non pacchettizzata**
   → seleziona la cartella **`<repo>/extension`** (path assoluto stampato da `install.py`).
2. Apri le **Opzioni** dell'estensione, incolla il **token** (`<repo>/data/ext_token`), URL
   `ws://127.0.0.1:8765/ext`.
3. Imposta `AUTOJOB_BROWSER_DRIVER=extension`.

In alternativa (dev), avvio automatico con estensione caricata + debug port:
```
python install.py --launch-browser
# oppure:  chrome.exe --load-extension="<repo>/extension" --remote-debugging-port=9222
```
