---
description: Avvia/garantisce il daemon AutoJob (LM Studio parte on-demand).
---
Esegui in shell `uv run autojob up` nella cartella del progetto AutoJob (avvia il daemon se non già
attivo). Poi verifica `http://127.0.0.1:8765/ready` e conferma all'utente che è pronto: cockpit su
`/`, MCP su `/mcp/`. Ricorda che LM Studio si avvia automaticamente al primo uso LLM e che il daemon
si spegne dopo 30 minuti di inattività (`uv run autojob down` per fermarlo subito).
