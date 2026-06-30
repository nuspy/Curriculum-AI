"""Client chat OpenAI-compatible (LM Studio :1234, Ollama :11434, ...).

Self-contained (httpx); interfaccia ispirata a ForexGPT ``llm_providers.BaseLLMProvider``.
Generazione ibrida: di default usa il modello locale; ``target="agent"`` (gestito a
livello di service) delega all'agente orchestratore restituendo il prompt composto.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx

from ..config.settings import get_settings


class LLMUnavailable(RuntimeError):
    """Il backend LLM locale non è raggiungibile / nessun modello caricato."""


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResult:
    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"
    response_time_ms: float = 0.0


def extract_json(text: str):
    """Estrae il primo oggetto/array JSON da una risposta LLM (tollerante ai code-fence)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        s = get_settings()
        self.base_url = (base_url or s.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else s.llm_api_key
        self.model = model or s.llm_model
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def _ensure_lms(self, *, force: bool = False) -> bool:
        """Autostart LM Studio + modello, se abilitato e provider locale. Best-effort."""
        s = get_settings()
        if s.lms_autostart and s.llm_provider == "lm_studio":
            from .lmstudio import manager

            await manager.ensure_loaded(self.model, force=force)
            return True
        return False

    async def _post(self, url: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"LLM non raggiungibile su {url}: {e}") from e

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResult:
        payload = {
            "model": model or self.model or "local-model",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)
        url = f"{self.base_url}/chat/completions"
        await self._ensure_lms()
        t0 = time.monotonic()
        try:
            data = await self._post(url, payload)
        except LLMUnavailable:
            if await self._ensure_lms(force=True):
                data = await self._post(url, payload)
            else:
                raise
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or ""
        return LLMResult(
            content=content,
            model=data.get("model", payload["model"]),
            usage=data.get("usage", {}) or {},
            finish_reason=choice.get("finish_reason", "stop"),
            response_time_ms=(time.monotonic() - t0) * 1000.0,
        )

    async def chat_json(self, messages: list[LLMMessage], **kwargs):
        """Come ``chat`` ma chiede e parsa JSON. Ritorna (raw_text, parsed_or_None)."""
        kwargs.setdefault("response_format", {"type": "json_object"})
        res = await self.chat(messages, **kwargs)
        return res.content, extract_json(res.content)

    async def test_connection(self) -> bool:
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url, headers=self._headers())
                return r.status_code == 200
        except httpx.HTTPError:
            return False


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
