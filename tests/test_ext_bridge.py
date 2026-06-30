from fastapi.testclient import TestClient

from autojob.browser.drivers.extension_driver import ExtensionDriver
from autojob.daemon import ext_token
from autojob.daemon.app import create_app


class FakeHub:
    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list = []

    async def send_command(self, type: str, payload=None, *, timeout: float = 30.0) -> dict:
        self.calls.append((type, payload))
        r = self.responses.get(type, {})
        return r(payload) if callable(r) else r


def test_ws_handshake_and_query_applied(temp_db):
    with TestClient(create_app()) as client:
        token = ext_token.get_token()
        with client.websocket_connect("/ext") as ws:
            ws.send_json({"v": 1, "id": "a1", "type": "auth", "payload": {"token": token}})
            assert ws.receive_json()["type"] == "auth_ok"

            ws.send_json({
                "id": "q1", "type": "query.applied",
                "payload": {"job_identity": {"title": "X", "company": "Y", "description": "d"}},
            })
            resp = ws.receive_json()
            assert resp["type"] == "applied_status"
            assert resp["corr"] == "q1"
            assert resp["payload"]["state"] == "none"


def test_ws_bad_token_rejected(temp_db):
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ext") as ws:
            ws.send_json({"type": "auth", "payload": {"token": "WRONG"}})
            assert ws.receive_json()["type"] == "auth_err"


async def test_extension_driver_with_fake_hub():
    hub = FakeHub({
        "cmd.get_snapshot": {
            "url": "http://x", "title": "Apply", "dom_hash": "h",
            "elements": [{"index": 0, "role": "textbox", "tag": "input", "label": "Full name"}],
            "forms": [], "frames": [],
        },
        "cmd.action": {"ok": True, "index": 0, "value_after": "Andrea"},
        "cmd.list_targets": {"targets": [{"target_id": "tab-1", "active": True, "url": "http://x"}]},
        "cmd.navigate": {"ok": True, "message": "navigated"},
    })
    drv = ExtensionDriver(hub=hub)

    snap = await drv.get_snapshot()
    assert snap.title == "Apply" and snap.elements[0].label == "Full name"

    r = await drv.fill(0, "Andrea")
    assert r.ok and r.value_after == "Andrea"

    targets = await drv.list_targets()
    assert targets and targets[0].target_id == "tab-1"

    assert await drv.attach() == "tab-1"
    assert ("cmd.action", {"op": "fill", "index": 0, "value": "Andrea"}) in hub.calls
