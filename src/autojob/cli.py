from __future__ import annotations

import argparse
import json

from . import __version__
from .config.settings import get_settings


def _info() -> dict:
    s = get_settings()
    return {
        "version": __version__,
        "host": s.host,
        "port": s.port,
        "db_file": str(s.db_file),
        "database_url": s.database_url,
        "browser_driver": s.browser_driver,
        "llm_provider": s.llm_provider,
        "embed_model": s.embed_model,
        "submit_mode": s.submit_mode,
        "reapply_policy": s.reapply_policy,
    }


def _base() -> str:
    s = get_settings()
    return f"http://{s.host}:{s.port}"


def _health_ok() -> bool:
    import httpx

    try:
        return httpx.get(_base() + "/health", timeout=2).status_code == 200
    except Exception:
        return False


def _up() -> None:
    import subprocess
    import sys
    import time

    if _health_ok():
        print(f"daemon gia attivo: {_base()}")
        return
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([sys.executable, "-m", "autojob.daemon.run"], creationflags=flags)
    for _ in range(40):
        if _health_ok():
            break
        time.sleep(0.5)
    print(f"daemon avviato: {_base()}" if _health_ok() else "avvio non confermato (controlla i log)")
    print("LM Studio verra avviato on-demand al primo uso LLM (autostart); idle-shutdown dopo 30m.")


def _down() -> None:
    import httpx

    try:
        print("shutdown:", httpx.post(_base() + "/admin/shutdown", timeout=10).json())
    except Exception as e:
        print("down: daemon forse gia spento o non raggiungibile:", str(e)[:120])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autojob", description="AutoJob CLI")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("version", help="stampa la versione")
    sub.add_parser("info", help="stampa configurazione e percorsi")
    sub.add_parser("serve", help="avvia il daemon (alias di autojobd)")
    sub.add_parser("up", help="avvia il daemon in background se non attivo")
    sub.add_parser("down", help="arresta daemon + LM Studio (idle/forzato)")
    args = parser.parse_args(argv)

    if args.cmd == "version":
        print(__version__)
    elif args.cmd == "info":
        print(json.dumps(_info(), indent=2, ensure_ascii=False))
    elif args.cmd == "serve":
        from .daemon.run import main as serve_main

        serve_main()
    elif args.cmd == "up":
        _up()
    elif args.cmd == "down":
        _down()
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
