"""Tracciamento attività + hook di spegnimento per l'idle-watchdog (requisito utente)."""

from __future__ import annotations

import time
from collections.abc import Callable

_last = time.monotonic()
_hook: Callable[[], None] | None = None


def touch() -> None:
    global _last
    _last = time.monotonic()


def idle_seconds() -> float:
    return time.monotonic() - _last


def set_shutdown_hook(fn: Callable[[], None]) -> None:
    global _hook
    _hook = fn


def trigger_shutdown() -> None:
    if _hook is not None:
        try:
            _hook()
        except Exception:  # noqa: BLE001
            pass


def should_shutdown(idle_s: float, *, enabled: bool, minutes: int) -> bool:
    return enabled and idle_s >= minutes * 60
