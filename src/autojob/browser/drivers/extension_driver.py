"""Driver browser via estensione MV3 sul bridge WS (piano §3, Fase 5).

Implementa la porta ``BrowserDriver`` inviando comandi all'estensione tramite l'hub;
la superficie dei tool resta identica a FakeDriver/PlaywrightDriver.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from ...daemon.ext_hub import get_hub
from ..port import ActionResult, CaptchaInfo, DomChange, TargetInfo
from ..snapshot import PageSnapshot, element_from_dict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ti(d: dict | None) -> TargetInfo | None:
    if not d:
        return None
    return TargetInfo(
        target_id=d.get("target_id", ""), type=d.get("type", "tab"), url=d.get("url", ""),
        title=d.get("title", ""), active=bool(d.get("active")), opener_id=d.get("opener_id"),
    )


def _ar(d: dict | None) -> ActionResult:
    d = d or {}
    return ActionResult(
        ok=bool(d.get("ok")), index=d.get("index"), message=d.get("message", ""),
        new_snapshot_id=d.get("new_snapshot_id"), dom_changed=bool(d.get("dom_changed")),
        error_kind=d.get("error_kind"), value_after=d.get("value_after"),
        opened_target=_ti(d.get("opened_target")),
    )


def _snap(d: dict | None) -> PageSnapshot:
    d = d or {}
    return PageSnapshot(
        snapshot_id=d.get("snapshot_id") or uuid.uuid4().hex,
        url=d.get("url", ""), title=d.get("title", ""),
        captured_at=d.get("captured_at") or _now_iso(),
        viewport=d.get("viewport", {}), dom_hash=d.get("dom_hash", ""),
        elements=[element_from_dict(e) for e in d.get("elements", [])],
        forms=d.get("forms", []), frames=d.get("frames", []),
        has_captcha_hint=bool(d.get("has_captcha_hint")),
    )


class ExtensionDriver:
    name = "extension"

    def __init__(self, hub=None):
        self._hub = hub or get_hub()

    async def _cmd(self, type: str, payload: dict | None = None) -> dict:
        return await self._hub.send_command(type, payload or {})

    async def attach(self, target: str | None = None) -> str:
        if target:
            await self._cmd("cmd.switch_target", {"target_id": target})
        try:
            r = await self._cmd("cmd.list_targets")
            targets = r.get("targets", [])
            return next((t["target_id"] for t in targets if t.get("active")),
                        targets[0]["target_id"] if targets else "active")
        except Exception:  # noqa: BLE001
            return "active"

    async def navigate(self, url: str, *, wait: bool = True) -> ActionResult:
        return _ar(await self._cmd("cmd.navigate", {"url": url, "wait": wait}))

    async def current_url(self) -> str:
        return (await self._cmd("cmd.current_url")).get("url", "")

    async def list_targets(self) -> list[TargetInfo]:
        r = await self._cmd("cmd.list_targets")
        return [t for t in (_ti(x) for x in r.get("targets", [])) if t]

    async def current_target(self) -> str:
        return (await self._cmd("cmd.current_target")).get("target_id", "active")

    async def switch_target(self, target_id: str) -> ActionResult:
        return _ar(await self._cmd("cmd.switch_target", {"target_id": target_id}))

    async def wait_for_new_target(
        self, *, since: Sequence[str] | None = None, timeout_ms: int = 8000
    ) -> TargetInfo | None:
        r = await self._cmd("cmd.wait_new_target", {"since": list(since or []), "timeout_ms": timeout_ms})
        return _ti(r.get("target"))

    async def close_target(self, target_id: str) -> ActionResult:
        return _ar(await self._cmd("cmd.close_target", {"target_id": target_id}))

    async def get_snapshot(self, *, viewport_only: bool = False, include_hidden: bool = False) -> PageSnapshot:
        return _snap(await self._cmd("cmd.get_snapshot", {"viewport_only": viewport_only, "include_hidden": include_hidden}))

    async def get_page_text(self) -> str:
        return (await self._cmd("cmd.page_text")).get("text", "")

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        r = await self._cmd("cmd.screenshot", {"full_page": full_page})
        b64 = r.get("base64")
        return base64.b64decode(b64) if b64 else b""

    async def click(self, index: int, *, expect_new_target: bool = False) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "click", "index": index, "expect_new_target": expect_new_target}))

    async def fill(self, index: int, value: str, *, trusted: bool = True, clear: bool = True) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "fill", "index": index, "value": value}))

    async def select_option(self, index: int, *, value: str | None = None, label: str | None = None) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "select", "index": index, "value": value, "label": label}))

    async def set_checkbox(self, index: int, checked: bool) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "checkbox", "index": index, "checked": checked}))

    async def upload_file(self, index: int, paths: Sequence[str]) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "upload", "index": index, "paths": list(paths)}))

    async def scroll(self, *, to_index: int | None = None, dy: int = 0, dx: int = 0) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "scroll", "index": to_index, "dy": dy, "dx": dx}))

    async def press_key(self, index: int | None, key: str) -> ActionResult:
        return _ar(await self._cmd("cmd.action", {"op": "key", "index": index, "key": key}))

    async def wait_for_dom_change(self, *, timeout_ms: int = 8000, expect_url_change: bool = False) -> DomChange:
        r = await self._cmd("cmd.wait_dom", {"timeout_ms": timeout_ms, "expect_url_change": expect_url_change})
        return DomChange(changed=bool(r.get("changed")), mutations=r.get("mutations", 0),
                         url_changed=bool(r.get("url_changed")), new_snapshot_id=r.get("new_snapshot_id"))

    async def eval_js(self, expr: str, *, world: str = "ISOLATED") -> object:
        return (await self._cmd("cmd.eval", {"expr": expr, "world": world})).get("result")

    async def detect_captcha(self) -> CaptchaInfo | None:
        r = await self._cmd("cmd.detect_captcha")
        if r.get("present"):
            return CaptchaInfo(present=True, kind=r.get("kind", "unknown"),
                               url=r.get("url", ""), hint=r.get("hint", ""))
        return None

    async def close(self) -> None:
        return None
