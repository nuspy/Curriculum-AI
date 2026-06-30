# AutoJob Bridge (estensione MV3)

Collega il daemon AutoJob al tuo browser reale loggato: snapshot indicizzato, azioni
"trusted", duplicate-guard col badge, handoff multi-tab.

## Caricamento (Chrome / Opera)
1. Avvia il daemon: `uv run autojobd` (oppure `autojob up`). Il token sta in `data/ext_token`.
2. `chrome://extensions` → attiva **Modalità sviluppatore** → **Carica estensione non pacchettizzata** → seleziona questa cartella `extension/`.
3. Apri le **Opzioni** dell'estensione, incolla il **token** e verifica l'URL `ws://127.0.0.1:8765/ext`.
4. Quando l'estensione è connessa, imposta sul daemon `AUTOJOB_BROWSER_DRIVER=extension`: i tool browser
   (`get_page_snapshot`, `fill_form_field`, `click_element`, …) useranno la **tua sessione Chrome reale**.

## Duplicate-guard
Su ogni pagina annuncio l'estensione interroga il daemon (`query.applied`); se hai già fatto domanda
appare un **badge rosso** (match forte) o **ambra** (possibile duplicato) sull'icona. L'invio resta possibile.

## Note tecniche
- Input "trusted": native-setter + dispatch nel **MAIN world**; upload CV via `chrome.debugger`
  (`DOM.setFileInputFiles`).
- Multi-tab: gli "Apply" che aprono un nuovo tab sono intercettati (handoff); il daemon può fare `switch_target`.
- Il service worker fa keepalive (~24s) e si riconnette automaticamente con backoff.
- Richiede Chrome ≥ 116 (WebSocket nel service worker).
