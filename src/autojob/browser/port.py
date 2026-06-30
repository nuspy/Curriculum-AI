"""Porta ``BrowserDriver`` — contratto di stabilità tra MCP e il browser (piano §2).

Implementata prima da driver MVP (CDP/claude-in-chrome), poi dall'estensione MV3,
senza cambiare la superficie dei tool. Tutte le azioni operano **per indice**.
Gestisce anche i bottoni "Apply" che aprono un nuovo tab/finestra (handoff target).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .snapshot import PageSnapshot


@dataclass
class TargetInfo:
    target_id: str
    type: str = "tab"  # tab | window | popup
    url: str = ""
    title: str = ""
    active: bool = False
    opener_id: str | None = None


@dataclass
class ActionResult:
    ok: bool
    index: int | None = None
    message: str = ""
    new_snapshot_id: str | None = None
    dom_changed: bool = False
    error_kind: str | None = None  # not_found | not_interactable | timeout | intervention
    value_after: str | None = None
    opened_target: TargetInfo | None = None  # valorizzato se l'azione ha aperto un tab/finestra


@dataclass
class DomChange:
    changed: bool
    mutations: int = 0
    url_changed: bool = False
    new_snapshot_id: str | None = None


@dataclass
class CaptchaInfo:
    present: bool
    kind: str = "unknown"  # recaptcha | hcaptcha | turnstile | unknown
    url: str = ""
    hint: str = ""


@runtime_checkable
class BrowserDriver(Protocol):
    name: str

    async def attach(self, target: str | None = None) -> str: ...
    async def navigate(self, url: str, *, wait: bool = True) -> ActionResult: ...
    async def current_url(self) -> str: ...

    # --- TABS / WINDOWS (intercetta "Apply" che apre un nuovo target) ---
    async def list_targets(self) -> list[TargetInfo]: ...
    async def current_target(self) -> str: ...
    async def switch_target(self, target_id: str) -> ActionResult: ...
    async def wait_for_new_target(
        self, *, since: Sequence[str] | None = None, timeout_ms: int = 8000
    ) -> TargetInfo | None: ...
    async def close_target(self, target_id: str) -> ActionResult: ...

    # --- READ ---
    async def get_snapshot(
        self, *, viewport_only: bool = False, include_hidden: bool = False
    ) -> PageSnapshot: ...
    async def get_page_text(self) -> str: ...
    async def screenshot(self, *, full_page: bool = False) -> bytes: ...

    # --- ACT (by index) ---
    async def click(self, index: int, *, expect_new_target: bool = False) -> ActionResult: ...
    async def fill(
        self, index: int, value: str, *, trusted: bool = True, clear: bool = True
    ) -> ActionResult: ...
    async def select_option(
        self, index: int, *, value: str | None = None, label: str | None = None
    ) -> ActionResult: ...
    async def set_checkbox(self, index: int, checked: bool) -> ActionResult: ...
    async def upload_file(self, index: int, paths: Sequence[str]) -> ActionResult: ...
    async def scroll(
        self, *, to_index: int | None = None, dy: int = 0, dx: int = 0
    ) -> ActionResult: ...
    async def press_key(self, index: int | None, key: str) -> ActionResult: ...

    # --- WAIT / VERIFY / ESCAPE ---
    async def wait_for_dom_change(
        self, *, timeout_ms: int = 8000, expect_url_change: bool = False
    ) -> DomChange: ...
    async def eval_js(self, expr: str, *, world: str = "ISOLATED") -> object: ...
    async def detect_captcha(self) -> CaptchaInfo | None: ...
    async def close(self) -> None: ...
