from fastapi.testclient import TestClient

from autojob.config import settings as sm
from autojob.core.lmstudio import LMStudioManager
from autojob.daemon import activity
from autojob.daemon.app import create_app


class FakeRunner:
    def __init__(self):
        self.calls: list = []
        self.server_running = False
        self.loaded = ""

    async def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        sub = args[1:]
        if sub[:2] == ["server", "status"]:
            return (0, "running" if self.server_running else "stopped", "")
        if sub[:2] == ["server", "start"]:
            self.server_running = True
            return (0, "started", "")
        if sub[:2] == ["server", "stop"]:
            self.server_running = False
            return (0, "stopped", "")
        if sub[:1] == ["ps"]:
            return (0, self.loaded, "")
        if sub[:1] == ["load"]:
            self.loaded += " " + sub[1]
            return (0, "ok", "")
        if sub[:1] == ["unload"]:
            return (0, "ok", "")
        return (0, "", "")


async def test_lmstudio_ensure_and_shutdown(monkeypatch):
    monkeypatch.setenv("AUTOJOB_LMS_AUTOSTART", "true")
    sm.get_settings.cache_clear()
    try:
        fr = FakeRunner()
        m = LMStudioManager(runner=fr)

        r = await m.ensure_loaded("qwen")
        assert r["ok"] and fr.server_running
        assert any(a[1:3] == ["server", "start"] for a in fr.calls)
        assert any(a[1] == "load" and a[2] == "qwen" for a in fr.calls)

        n = len(fr.calls)
        await m.ensure_loaded("qwen")  # cached → nessun nuovo comando
        assert len(fr.calls) == n

        await m.shutdown()
        assert any(a[1] == "unload" for a in fr.calls)
        assert any(a[1:3] == ["server", "stop"] for a in fr.calls)
        assert not fr.server_running
    finally:
        sm.get_settings.cache_clear()


async def test_lmstudio_autostart_off(monkeypatch):
    monkeypatch.setenv("AUTOJOB_LMS_AUTOSTART", "false")
    sm.get_settings.cache_clear()
    try:
        m = LMStudioManager(runner=FakeRunner())
        r = await m.ensure_loaded("qwen")
        assert r.get("skipped") == "autostart_off"
    finally:
        sm.get_settings.cache_clear()


def test_should_shutdown_logic():
    assert activity.should_shutdown(31 * 60, enabled=True, minutes=30) is True
    assert activity.should_shutdown(10 * 60, enabled=True, minutes=30) is False
    assert activity.should_shutdown(99 * 60, enabled=False, minutes=30) is False


def test_admin_shutdown_endpoint(temp_db):
    with TestClient(create_app()) as client:
        r = client.post("/admin/shutdown")
        assert r.status_code == 200
        assert r.json()["ok"] is True
