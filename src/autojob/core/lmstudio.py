"""Gestione lifecycle di LM Studio via CLI ``lms`` (requisito utente).

Avvia il server e carica il modello di default on-demand; allo spegnimento ferma SOLO
ciò che AutoJob ha avviato. Il ``runner`` è iniettabile per i test.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from ..config.settings import get_settings
from ..utils.logging import get_logger

Runner = Callable[[list], Awaitable[tuple]]


async def _default_runner(args: list) -> tuple:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return proc.returncode, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")


def _norm(s: str) -> str:
    return (s or "").lower()


class LMStudioManager:
    def __init__(self, runner: Runner | None = None):
        self._run: Runner = runner or _default_runner
        self._loaded: set[str] = set()
        self._we_loaded: set[str] = set()
        self._server_ok = False
        self._started_server = False

    async def _cmd(self, *args: str) -> tuple:
        return await self._run([get_settings().lms_cli, *args])

    async def server_up(self) -> bool:
        rc, out, err = await self._cmd("server", "status")
        text = _norm(out + err)
        return rc == 0 and ("running" in text or "started" in text or "on)" in text)

    async def _loaded_text(self) -> str:
        rc, out, _ = await self._cmd("ps")
        return out if rc == 0 else ""

    async def ensure_loaded(self, model: str | None = None, *, force: bool = False) -> dict:
        s = get_settings()
        if not s.lms_autostart:
            return {"ok": True, "skipped": "autostart_off"}
        model = model or s.lms_model or s.llm_model or ""
        if not force and self._server_ok and (not model or model in self._loaded):
            return {"ok": True, "cached": True, "model": model}

        log = get_logger()
        result: dict = {"model": model}
        try:
            if force or not self._server_ok:
                if not await self.server_up():
                    await self._cmd("server", "start")
                    self._started_server = True
                    result["server"] = "started"
                    log.info("LM Studio: server avviato")
                else:
                    result["server"] = "already_up"
                self._server_ok = True
            if model and model not in self._loaded:
                if _norm(model) in _norm(await self._loaded_text()):
                    self._loaded.add(model)
                    result["model"] = "already_loaded"
                else:
                    load_args = ["load", model, "-y"]
                    if s.lms_context_length and "embed" not in _norm(model):
                        load_args += ["-c", str(s.lms_context_length)]
                    if s.lms_gpu:
                        load_args += ["--gpu", s.lms_gpu]
                    rc, out, err = await self._cmd(*load_args)
                    if rc == 0:
                        self._loaded.add(model)
                        self._we_loaded.add(model)
                        result["model_loaded"] = True
                        log.info(f"LM Studio: modello caricato ({model})")
                    else:
                        result["model_load_error"] = (err or out)[:200]
            result["ok"] = True
        except FileNotFoundError:
            return {"ok": False, "reason": "lms_not_found"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "reason": str(e)[:200]}
        return result

    async def shutdown(self) -> dict:
        out: dict = {}
        try:
            for m in list(self._we_loaded):
                await self._cmd("unload", m)
                out.setdefault("unloaded", []).append(m)
            if self._started_server:
                await self._cmd("server", "stop")
                out["server"] = "stopped"
        except FileNotFoundError:
            out["reason"] = "lms_not_found"
        except Exception as e:  # noqa: BLE001
            out["error"] = str(e)[:200]
        self._loaded.clear()
        self._we_loaded.clear()
        self._server_ok = False
        self._started_server = False
        return out


manager = LMStudioManager()
