"""Fake LLM/embeddings client per test ermetici (nessuna chiamata di rete)."""

from __future__ import annotations

import hashlib
import json

from autojob.llm.client import LLMResult


class FakeLLM:
    def __init__(self, json_obj=None, text="COVER LETTER / ANSWER TEXT"):
        self._json = json_obj
        self._text = text

    async def chat_json(self, messages, **kwargs):
        return json.dumps(self._json), self._json

    async def chat(self, messages, **kwargs) -> LLMResult:
        return LLMResult(content=self._text, model="fake-model")


class FakeEmb:
    async def embed_one(self, text: str) -> list[float]:
        h = hashlib.sha256((text or "").encode("utf-8")).digest()
        return [b / 255.0 for b in h[:16]]

    async def embed(self, texts):
        return [await self.embed_one(t) for t in texts]
