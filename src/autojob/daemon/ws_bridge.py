"""Bridge WebSocket per l'estensione MV3 (piano §3): ``/ext``.

Handshake a token, instradamento risposte per ``corr``, e gestione eventi
(``query.applied`` → duplicate-guard, ``intervention_needed`` → record, ping/pong).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..utils.logging import get_logger
from .ext_hub import get_hub
from .ext_token import get_token

router = APIRouter()


@router.websocket("/ext")
async def ext_ws(ws: WebSocket) -> None:
    log = get_logger()
    hub = get_hub()
    await ws.accept()

    try:
        first = await ws.receive_json()
    except Exception:  # noqa: BLE001
        await ws.close(code=4400)
        return

    if first.get("type") != "auth" or (first.get("payload") or {}).get("token") != get_token():
        await ws.send_json({"type": "auth_err", "payload": {"reason": "bad_token"}})
        await ws.close(code=4401)
        return

    await ws.send_json({"type": "auth_ok", "payload": {"service": "autojob"}})
    hub.attach(ws.send_json)
    log.info("Estensione connessa al bridge /ext")

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            corr = msg.get("corr")

            if corr and hub.has_pending(corr):
                hub.resolve(corr, msg.get("payload") or {})
                continue

            if mtype == "query.applied":
                from ..core.application_service import check_application_status

                payload = msg.get("payload") or {}
                ident = payload.get("job_identity") or payload
                st = check_application_status(ident)
                await ws.send_json({"type": "applied_status", "corr": msg.get("id"), "payload": st})
            elif mtype == "intervention_needed":
                from ..core.intervention_service import record_intervention

                pl = msg.get("payload") or {}
                record_intervention(
                    type=pl.get("kind", "captcha"),
                    prompt=pl.get("hint") or pl.get("url") or "intervento richiesto",
                )
            elif mtype == "ping":
                await ws.send_json({"type": "pong", "payload": {}})
            # snapshot/action_result/dom_changed/target_opened non correlati: ignorati
    except WebSocketDisconnect:
        pass
    finally:
        hub.detach()
        log.info("Estensione disconnessa dal bridge /ext")
