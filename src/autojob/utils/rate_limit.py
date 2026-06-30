from __future__ import annotations

import asyncio
import random
import time


class RateLimiter:
    """Limitatore a misura umana: intervallo minimo per chiave (es. portale) + jitter casuale.

    Riduce il rischio di rilevamento mantenendo un ritmo non robotico. Usato in Fase 4.
    """

    def __init__(self, min_interval_s: float = 3.0, jitter_s: float = 2.0):
        self.min_interval_s = min_interval_s
        self.jitter_s = jitter_s
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        return lock

    async def wait(self, key: str = "default") -> float:
        """Attende, se necessario, prima di permettere la prossima azione per ``key``.

        Ritorna i secondi effettivamente attesi.
        """
        async with self._lock(key):
            now = time.monotonic()
            last = self._last.get(key, 0.0)
            target = last + self.min_interval_s + random.uniform(0.0, self.jitter_s)
            delay = max(0.0, target - now)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last[key] = time.monotonic()
            return delay
