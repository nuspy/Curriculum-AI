---
description: Prepara (e solo su conferma esplicita invia) una candidatura.
argument-hint: <match_id oppure url annuncio>
---
Usa la skill `autojob`. Garantisci il daemon e un browser driver reale (`AUTOJOB_BROWSER_DRIVER`
= `playwright` o `extension`). Per "$ARGUMENTS": apri la pagina con `navigate(url)`, poi `analyze_form`
e `fill_application(job_id)` — che **NON invia** in modalità manual. Riporta lo stato risultante
(filled / needs_user / captcha / ready_for_review). Se `needs_user`, chiedi i dati mancanti all'utente
e riprova; se `captcha`, fermati e usa `request_user_intervention`. Invia con
`submit_application(application_id, force=true)` **solo dopo conferma esplicita** dell'utente.
