"""Hub del bridge estensione: invio comandi correlati per ``id`` + risoluzione risposte.

Una sola estensione connessa per volta (daemon single-process). Il WS route alimenta
``resolve``/eventi; ``ExtensionDriver`` usa ``send_command``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class ExtNotConnected(RuntimeError):
    """Nessuna estensione connessa al bridge /ext."""


class ExtHub:
    def __init__(self) -> None:
        self._send: Callable[[dict], Awaitable[None]] | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._counter = 0

    def connected(self) -> bool:
        return self._send is not None

    def attach(self, send_callable: Callable[[dict], Awaitable[None]]) -> None:
        self._send = send_callable

    def detach(self) -> None:
        self._send = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ExtNotConnected("estensione disconnessa"))
        self._pending.clear()

    def has_pending(self, corr: str) -> bool:
        return corr in self._pending

    def resolve(self, corr: str, payload: dict) -> None:
        fut = self._pending.get(corr)
        if fut and not fut.done():
            fut.set_result(payload or {})

    async def send_command(
        self, type: str, payload: dict | None = None, *, timeout: float = 30.0
    ) -> dict:
        if self._send is None:
            raise ExtNotConnected("nessuna estensione connessa")
        self._counter += 1
        cid = f"cmd-{self._counter}"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[cid] = fut
        await self._send({"v": 1, "id": cid, "type": type, "payload": payload or {}})
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(cid, None)


hub = ExtHub()


def get_hub() -> ExtHub:
    return hub
