"""Client embeddings OpenAI-compatible (``/v1/embeddings``) per il matching CV↔annuncio.

Modello di default multilingue (bge-m3) via LM Studio/Ollama. I vettori vanno in
``*_vec`` (sqlite-vec); per pochi annunci il ranking usa anche ``cosine`` in Python.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import httpx

from ..config.settings import get_settings


class EmbeddingsUnavailable(RuntimeError):
    """Il backend embeddings non è raggiungibile / modello non caricato."""


class EmbeddingsClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dim: int | None = None,
        timeout: float = 60.0,
    ):
        s = get_settings()
        self.base_url = (base_url or s.embed_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else s.embed_api_key
        self.model = model or s.embed_model
        self.dim = dim or s.embed_dim
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def _ensure_lms(self, *, force: bool = False) -> bool:
        s = get_settings()
        if s.lms_autostart and "1234" in (self.base_url or ""):
            from ..core.lmstudio import manager

            await manager.ensure_loaded(self.model, force=force)
            return True
        return False

    async def _post(self, url: str, texts) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url, json={"model": self.model, "input": list(texts)}, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            raise EmbeddingsUnavailable(f"Embeddings non raggiungibili su {url}: {e}") from e

    async def embed(self, texts: str | Sequence[str]) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        url = f"{self.base_url}/embeddings"
        await self._ensure_lms()
        try:
            data = await self._post(url, texts)
        except EmbeddingsUnavailable:
            if await self._ensure_lms(force=True):
                data = await self._post(url, texts)
            else:
                raise
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [it["embedding"] for it in items]

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]

    async def test_connection(self) -> bool:
        try:
            return len(await self.embed_one("ping")) > 0
        except EmbeddingsUnavailable:
            return False


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


_emb: EmbeddingsClient | None = None


def get_embeddings_client() -> EmbeddingsClient:
    global _emb
    if _emb is None:
        _emb = EmbeddingsClient()
    return _emb
