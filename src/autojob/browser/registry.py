from __future__ import annotations

from ..config.settings import get_settings
from .port import BrowserDriver

_LATER_PHASES = {"cdp_mcp", "claude_chrome"}


def get_driver(name: str | None = None) -> BrowserDriver:
    """Risolve il driver browser dalla config (``AUTOJOB_BROWSER_DRIVER``).

    Fase 0: solo ``fake``. I driver MVP/estensione arrivano nelle fasi 2/3/5.
    """
    drv = (name or get_settings().browser_driver).lower()
    if drv == "fake":
        from .drivers.fake_driver import FakeDriver

        return FakeDriver()
    if drv == "playwright":
        from .drivers.playwright_driver import PlaywrightDriver

        return PlaywrightDriver()
    if drv == "extension":
        from .drivers.extension_driver import ExtensionDriver

        return ExtensionDriver()
    if drv in _LATER_PHASES:
        raise NotImplementedError(
            f"Driver '{drv}' previsto in una fase successiva (vedi roadmap §10). Usa 'fake' per ora."
        )
    raise ValueError(f"Driver sconosciuto: {drv!r}")
