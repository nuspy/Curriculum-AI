"""Driver browser MVP basato su Playwright (piano §2, Fase 2).

Connette via CDP alla Chrome reale loggata (``AUTOJOB_CDP_URL``, es.
``http://127.0.0.1:9222``) oppure lancia un chromium per dev/test. Implementa la porta
``BrowserDriver`` (read + tab/handoff + azioni base); lo snapshot usa ``SNAPSHOT_JS``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from ...config.settings import get_settings
from ..port import ActionResult, CaptchaInfo, DomChange, TargetInfo
from ..snapshot import ElementNode, PageSnapshot
from ..snapshot_js import SNAPSHOT_JS

_EL_FIELDS = {f.name for f in dataclasses.fields(ElementNode)}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node(e: dict) -> ElementNode:
    return ElementNode(**{k: v for k, v in e.items() if k in _EL_FIELDS})


class PlaywrightDriver:
    name = "playwright"

    def __init__(self, cdp_url: str | None = None, headless: bool | None = None):
        s = get_settings()
        self.cdp_url = cdp_url if cdp_url is not None else s.cdp_url
        self.headless = s.browser_headless if headless is None else headless
        self._pw = None
        self._browser = None
        self._context = None
        self._targets: dict[str, object] = {}
        self._ids: dict[int, str] = {}
        self._counter = 0
        self._current: str | None = None
        self._started = False

    # ---------- lifecycle ----------
    async def start(self) -> None:
        if self._started:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        if self.cdp_url:
            self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
            self._context = (
                self._browser.contexts[0]
                if self._browser.contexts
                else await self._browser.new_context()
            )
        else:
            self._browser = await self._pw.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
        self._context.on("page", self._register)
        if not self._context.pages:
            await self._context.new_page()
        self._sync_pages()
        self._current = next(iter(self._targets), None)
        self._started = True

    async def _ensure(self) -> None:
        if not self._started:
            await self.start()

    def _register(self, page) -> str:
        key = id(page)
        if key in self._ids:
            return self._ids[key]
        self._counter += 1
        tid = f"tab-{self._counter}"
        self._targets[tid] = page
        self._ids[key] = tid
        return tid

    def _sync_pages(self) -> None:
        if self._context:
            for p in self._context.pages:
                self._register(p)

    def _page(self, target_id: str | None = None):
        return self._targets.get(target_id or self._current)

    # ---------- nav / tabs ----------
    async def attach(self, target: str | None = None) -> str:
        await self._ensure()
        if target and target in self._targets:
            self._current = target
        return self._current

    async def navigate(self, url: str, *, wait: bool = True) -> ActionResult:
        await self._ensure()
        try:
            await self._page().goto(
                url, wait_until=("domcontentloaded" if wait else "commit"), timeout=30000
            )
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, error_kind="timeout", message=str(e)[:200])
        return ActionResult(ok=True, message="navigated")

    async def current_url(self) -> str:
        await self._ensure()
        return self._page().url

    async def list_targets(self) -> list[TargetInfo]:
        await self._ensure()
        self._sync_pages()
        res = []
        for tid, pg in list(self._targets.items()):
            try:
                url, title = pg.url, await pg.title()
            except Exception:  # noqa: BLE001
                url, title = "", ""
            res.append(TargetInfo(tid, "tab", url, title, active=(tid == self._current)))
        return res

    async def current_target(self) -> str:
        await self._ensure()
        return self._current

    async def switch_target(self, target_id: str) -> ActionResult:
        await self._ensure()
        if target_id not in self._targets:
            return ActionResult(ok=False, error_kind="not_found")
        self._current = target_id
        try:
            await self._targets[target_id].bring_to_front()
        except Exception:  # noqa: BLE001
            pass
        return ActionResult(ok=True, message=f"switched->{target_id}")

    async def wait_for_new_target(
        self, *, since: Sequence[str] | None = None, timeout_ms: int = 8000
    ) -> TargetInfo | None:
        await self._ensure()
        known = set(since or [])
        for _ in range(max(1, int(timeout_ms / 100))):
            self._sync_pages()
            for tid, pg in self._targets.items():
                if tid not in known:
                    try:
                        await pg.wait_for_load_state("domcontentloaded", timeout=3000)
                    except Exception:  # noqa: BLE001
                        pass
                    return TargetInfo(tid, "tab", pg.url, "", active=False)
            await asyncio.sleep(0.1)
        return None

    async def close_target(self, target_id: str) -> ActionResult:
        pg = self._targets.get(target_id)
        if not pg:
            return ActionResult(ok=False, error_kind="not_found")
        try:
            await pg.close()
        except Exception:  # noqa: BLE001
            pass
        self._targets.pop(target_id, None)
        self._ids.pop(id(pg), None)
        if self._current == target_id:
            self._current = next(iter(self._targets), None)
        return ActionResult(ok=True)

    # ---------- read ----------
    async def get_snapshot(self, *, viewport_only: bool = False, include_hidden: bool = False) -> PageSnapshot:
        await self._ensure()
        data = await self._page().evaluate(SNAPSHOT_JS)
        return PageSnapshot(
            snapshot_id=uuid.uuid4().hex,
            url=data.get("url", ""),
            title=data.get("title", ""),
            captured_at=_now_iso(),
            viewport=data.get("viewport", {}),
            dom_hash=data.get("dom_hash", ""),
            elements=[_node(e) for e in data.get("elements", [])],
            forms=data.get("forms", []),
            frames=data.get("frames", []),
            has_captcha_hint=bool(data.get("has_captcha_hint", False)),
        )

    async def get_page_text(self) -> str:
        await self._ensure()
        try:
            return await self._page().inner_text("body")
        except Exception:  # noqa: BLE001
            return await self._page().evaluate("document.body ? document.body.innerText : ''")

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        await self._ensure()
        return await self._page().screenshot(full_page=full_page)

    # ---------- act ----------
    def _loc(self, index: int):
        return self._page().locator(f'[data-aj-index="{index}"]')

    @staticmethod
    def _err_kind(e: Exception) -> str:
        msg = str(e).lower()
        return "not_found" if ("no element" in msg or "not found" in msg or "resolve" in msg) else "not_interactable"

    async def click(self, index: int, *, expect_new_target: bool = False) -> ActionResult:
        await self._ensure()
        try:
            if expect_new_target:
                before = set(self._targets.keys())
                await self._loc(index).click(timeout=8000)
                newt = await self.wait_for_new_target(since=before, timeout_ms=3000)
                return ActionResult(ok=True, index=index, dom_changed=True, opened_target=newt)
            await self._loc(index).click(timeout=8000)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, dom_changed=True)

    async def fill(self, index: int, value: str, *, trusted: bool = True, clear: bool = True) -> ActionResult:
        await self._ensure()
        try:
            await self._loc(index).fill(value, timeout=8000)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, value_after=value, dom_changed=True)

    async def select_option(self, index: int, *, value: str | None = None, label: str | None = None) -> ActionResult:
        await self._ensure()
        try:
            if value is not None:
                chosen = await self._loc(index).select_option(value=value, timeout=8000)
            elif label is not None:
                chosen = await self._loc(index).select_option(label=label, timeout=8000)
            else:
                return ActionResult(ok=False, index=index, message="value o label richiesto")
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, value_after=(chosen[0] if chosen else None))

    async def set_checkbox(self, index: int, checked: bool) -> ActionResult:
        await self._ensure()
        try:
            await self._loc(index).set_checked(checked, timeout=8000)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, value_after=str(checked))

    async def upload_file(self, index: int, paths: Sequence[str]) -> ActionResult:
        await self._ensure()
        try:
            await self._loc(index).set_input_files(list(paths), timeout=8000)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, value_after=";".join(paths))

    async def scroll(self, *, to_index: int | None = None, dy: int = 0, dx: int = 0) -> ActionResult:
        await self._ensure()
        try:
            if to_index is not None:
                await self._loc(to_index).scroll_into_view_if_needed(timeout=8000)
            else:
                await self._page().mouse.wheel(dx, dy)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=to_index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=to_index)

    async def press_key(self, index: int | None, key: str) -> ActionResult:
        await self._ensure()
        try:
            if index is not None:
                await self._loc(index).press(key, timeout=8000)
            else:
                await self._page().keyboard.press(key)
        except Exception as e:  # noqa: BLE001
            return ActionResult(ok=False, index=index, error_kind=self._err_kind(e), message=str(e)[:200])
        return ActionResult(ok=True, index=index, message=f"key:{key}")

    # ---------- wait / verify / escape ----------
    async def wait_for_dom_change(self, *, timeout_ms: int = 8000, expect_url_change: bool = False) -> DomChange:
        await self._ensure()
        pg = self._page()
        start_url = pg.url
        start_sig = await pg.evaluate("(document.body ? document.body.innerHTML.length : 0)")
        for _ in range(max(1, int(timeout_ms / 150))):
            await asyncio.sleep(0.15)
            cur_url = pg.url
            if expect_url_change and cur_url != start_url:
                return DomChange(changed=True, url_changed=True)
            cur_sig = await pg.evaluate("(document.body ? document.body.innerHTML.length : 0)")
            if cur_sig != start_sig or cur_url != start_url:
                return DomChange(changed=True, url_changed=(cur_url != start_url), mutations=abs(cur_sig - start_sig))
        return DomChange(changed=False)

    async def eval_js(self, expr: str, *, world: str = "ISOLATED") -> object:
        await self._ensure()
        return await self._page().evaluate(expr)

    async def detect_captcha(self) -> CaptchaInfo | None:
        await self._ensure()
        pg = self._page()
        try:
            has = await pg.evaluate(
                "/recaptcha|hcaptcha|turnstile|g-recaptcha|cf-challenge/i.test(document.documentElement.outerHTML)"
            )
        except Exception:  # noqa: BLE001
            has = False
        if has:
            return CaptchaInfo(present=True, kind="unknown", url=pg.url, hint="anti-bot gate rilevato")
        return None

    async def close(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()
        self._started = False
