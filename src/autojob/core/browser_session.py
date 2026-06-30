"""Sessione browser del daemon: singleton lazy del ``BrowserDriver`` + cache snapshot.

Il daemon è un unico processo, quindi un driver condiviso è sufficiente. ``attach()``
inizializza sia FakeDriver sia PlaywrightDriver (che avvia il browser al primo uso).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..browser.port import BrowserDriver
from ..browser.registry import get_driver
from ..db.models.browser import PageSnapshot as PageSnapshotRow
from ..db.session import get_session

_driver: BrowserDriver | None = None
_lock = asyncio.Lock()


async def get_session_driver() -> BrowserDriver:
    global _driver
    async with _lock:
        if _driver is None:
            d = get_driver()
            await d.attach()
            _driver = d
    return _driver


async def reset_session_driver() -> None:
    global _driver
    if _driver is not None:
        try:
            await _driver.close()
        except Exception:  # noqa: BLE001
            pass
        _driver = None


async def snapshot(viewport_only: bool = False, *, persist: bool = True) -> dict:
    """Cattura lo snapshot della pagina corrente e (opzionale) lo salva in page_snapshots."""
    drv = await get_session_driver()
    snap = await drv.get_snapshot(viewport_only=viewport_only)
    data = snap.to_dict()
    if persist:
        with get_session() as s:
            row = PageSnapshotRow(
                url=snap.url,
                title=snap.title,
                snapshot_json=data,
                dom_hash=snap.dom_hash,
                viewport=snap.viewport,
                frames=snap.frames,
                captured_at=datetime.now(timezone.utc),
            )
            s.add(row)
            s.flush()
            data["db_id"] = row.id
    return data
