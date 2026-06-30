#!/usr/bin/env python3
"""Installer AutoJob per agenti (e umani).

Esegue tutto ciò che serve a rendere AutoJob pronto all'uso:
uv sync → chromium (Playwright) → migrazioni DB → skill globali → registrazione MCP → avvio daemon.

Uso tipico (da dentro la cartella del repo):
    python install.py                # installazione completa (MCP scope utente, avvia il daemon)
    python install.py --check        # solo verifica ambiente, nessuna modifica
    python install.py --no-daemon --no-browser --mcp-scope project
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent


def have(exe: str) -> bool:
    return shutil.which(exe) is not None


def run(cmd: list[str]) -> int:
    print("   $", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(REPO)).returncode


def step(msg: str) -> None:
    print(f"[autojob] {msg}")


def check() -> int:
    step("CHECK ambiente (nessuna modifica)")
    items = {
        "uv": have("uv"),
        "claude CLI (opzionale)": have("claude"),
        "pyproject.toml": (REPO / "pyproject.toml").exists(),
        "alembic.ini": (REPO / "alembic.ini").exists(),
        "skill sorgente": (REPO / "skills" / "autojob" / "SKILL.md").exists(),
        "plugin manifest": (REPO / ".claude-plugin" / "plugin.json").exists(),
    }
    for k, v in items.items():
        print(f"   {'ok ' if v else 'NO '} {k}")
    if not items["uv"]:
        print("   -> Installa uv: https://docs.astral.sh/uv/")
    return 0 if items["uv"] and items["pyproject.toml"] else 1


def install(args: argparse.Namespace) -> int:
    if not have("uv"):
        print("ERRORE: 'uv' non trovato. Installa uv (https://docs.astral.sh/uv/) e riprova.")
        return 1

    step("uv sync (dipendenze)…")
    if run(["uv", "sync"]) != 0:
        return 1

    if not args.no_browser:
        step("playwright install chromium (browser reale)…")
        run(["uv", "run", "playwright", "install", "chromium"])

    step("alembic upgrade head (DB SQLite + tabelle vec0)…")
    if run(["uv", "run", "alembic", "upgrade", "head"]) != 0:
        return 1

    if not args.no_skills:
        src = REPO / "skills" / "autojob"
        dst = Path.home() / ".claude" / "skills" / "autojob"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        step(f"skill installata in {dst}")

    if args.mcp_scope != "none":
        if have("claude"):
            step(f"registro MCP (claude mcp add, scope={args.mcp_scope})…")
            run([
                "claude", "mcp", "add", "--transport", "http",
                "autojob", "http://127.0.0.1:8765/mcp/", "--scope", args.mcp_scope,
            ])
        else:
            step("CLI 'claude' assente: MCP resta via il .mcp.json del progetto.")
            print("   Per scope utente: claude mcp add --transport http autojob "
                  "http://127.0.0.1:8765/mcp/ --scope user")

    if not args.no_daemon:
        step("avvio daemon (autojob up)…")
        run(["uv", "run", "autojob", "up"])

    token = REPO / "data" / "ext_token"
    print("\n[autojob] INSTALLAZIONE COMPLETATA")
    print("   Cockpit:  http://127.0.0.1:8765/")
    print("   MCP:      http://127.0.0.1:8765/mcp/   (server 'autojob')")
    print("   Token estensione:", str(token) if token.exists() else "(creato al primo avvio del daemon)")
    print("   Skill: /autojob   Comandi: /autojob-up /autojob-search /autojob-apply /autojob-status")
    print("   Manuale: how_to_use.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install.py", description="Installer AutoJob")
    p.add_argument("--check", action="store_true", help="verifica l'ambiente senza modifiche")
    p.add_argument("--no-daemon", action="store_true", help="non avviare il daemon")
    p.add_argument("--no-skills", action="store_true", help="non copiare la skill in ~/.claude/skills")
    p.add_argument("--no-browser", action="store_true", help="salta il download di chromium")
    p.add_argument(
        "--mcp-scope", choices=["user", "project", "none"], default="user",
        help="scope di registrazione del server MCP (default: user)",
    )
    args = p.parse_args(argv)
    return check() if args.check else install(args)


if __name__ == "__main__":
    raise SystemExit(main())
