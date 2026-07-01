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
import os
import re
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


_BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Opera\opera.exe",
]


def _find_browser() -> str | None:
    for name in ("chrome", "chrome.exe", "opera", "opera.exe", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    local = Path.home() / "AppData" / "Local"
    for cand in [*_BROWSER_CANDIDATES,
                 str(local / "Google/Chrome/Application/chrome.exe"),
                 str(local / "Programs/Opera/opera.exe")]:
        if Path(cand).exists():
            return cand
    return None


def print_extension_help(ext_dir: Path, token: Path) -> None:
    print("\n[autojob] ESTENSIONE BROWSER (MV3) — caricamento manuale (Chrome non installa da CLI)")
    print(f"   Cartella da caricare: {ext_dir}")
    print("   1) chrome://extensions -> Modalita sviluppatore -> 'Carica estensione non pacchettizzata'")
    print("      -> seleziona la cartella qui sopra")
    print("   2) Opzioni estensione: incolla il token; URL ws://127.0.0.1:8765/ext")
    if token.exists():
        print(f"   Token: {token.read_text(encoding='utf-8').strip()}   (file: {token})")
    else:
        print(f"   Token: creato al primo avvio del daemon in {token}")
    print("   3) imposta AUTOJOB_BROWSER_DRIVER=extension")
    print(f'   Dev auto-load: chrome.exe --load-extension="{ext_dir}" --remote-debugging-port=9222')


def launch_browser(ext_dir: Path) -> None:
    exe = _find_browser()
    args = [f"--load-extension={ext_dir}", "--remote-debugging-port=9222"]
    if exe:
        step(f"avvio browser con estensione caricata: {exe}")
        subprocess.Popen([exe, *args])
        print("   (browser avviato con --load-extension e --remote-debugging-port=9222)")
    else:
        print("   Browser non trovato sul PATH/percorsi noti. Avvialo manualmente:")
        print(f'   chrome.exe --load-extension="{ext_dir}" --remote-debugging-port=9222')


def _detect_cv() -> str | None:
    """Cerca un CV nelle cartelle utente comuni (best-effort)."""
    home = Path.home()
    hits: list[Path] = []
    for d in (home / "Documents", home / "Desktop", home / "Downloads"):
        if not d.exists():
            continue
        for pat in ("*cv*", "*resume*", "*curriculum*"):
            for ext in ("pdf", "docx"):
                hits += [p for p in d.glob(f"{pat}.{ext}") if p.is_file()]
    if not hits:
        return None
    return str(max(hits, key=lambda p: p.stat().st_mtime))


def ensure_env(driver: str) -> None:
    """Genera/aggiorna .env in automatico (browser driver + CV rilevato)."""
    env = REPO / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else [
        "# AutoJob — configurazione (generata da install.py)"
    ]

    def upsert(key: str, val: str) -> None:
        for i, ln in enumerate(lines):
            if ln.strip().startswith(key + "="):
                lines[i] = f"{key}={val}"
                return
        lines.append(f"{key}={val}")

    upsert("AUTOJOB_BROWSER_DRIVER", driver)
    cv = _detect_cv()
    if cv:
        upsert("AUTOJOB_CV_PATH", cv.replace("\\", "/"))
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    step(f".env aggiornato (AUTOJOB_BROWSER_DRIVER={driver}{', CV rilevato' if cv else ''})")


def wire_hermes_mcp() -> None:
    """Registra il server MCP AutoJob nel config.yaml di Hermes (se presente), preservando i commenti."""
    localapp = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    roaming = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    candidates = [
        localapp / "hermes" / "config.yaml",
        Path.home() / ".hermes" / "config.yaml",
        roaming / "hermes" / "config.yaml",
    ]
    cfg = next((c for c in candidates if c.exists()), None)
    if not cfg:
        return  # Hermes non installato: nulla da fare
    text = cfg.read_text(encoding="utf-8")
    if "127.0.0.1:8765/mcp" in text:
        step("Hermes: MCP autojob già presente")
        return
    block = (
        "  autojob:\n"
        "    url: http://127.0.0.1:8765/mcp/\n"
        "    timeout: 120\n"
        "    connect_timeout: 60\n"
    )
    if re.search(r"(?m)^mcp_servers:[ \t]*$", text):
        text = re.sub(r"(?m)^(mcp_servers:[ \t]*\n)", r"\1" + block, text, count=1)
    else:
        text = text.rstrip() + "\n\nmcp_servers:\n" + block
    cfg.write_text(text, encoding="utf-8")
    step(f"Hermes: MCP autojob registrato in {cfg}")


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

    # Config automatica: .env (driver + CV) e MCP in Hermes — nessun passo manuale.
    ensure_env(args.browser_driver)
    wire_hermes_mcp()

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

    print_extension_help(REPO / "extension", token)
    if args.launch_browser:
        launch_browser(REPO / "extension")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install.py", description="Installer AutoJob")
    p.add_argument("--check", action="store_true", help="verifica l'ambiente senza modifiche")
    p.add_argument("--no-daemon", action="store_true", help="non avviare il daemon")
    p.add_argument("--no-skills", action="store_true", help="non copiare la skill in ~/.claude/skills")
    p.add_argument("--no-browser", action="store_true", help="salta il download di chromium")
    p.add_argument(
        "--launch-browser", action="store_true",
        help="avvia Chrome/Opera con l'estensione caricata + --remote-debugging-port=9222",
    )
    p.add_argument(
        "--mcp-scope", choices=["user", "project", "none"], default="user",
        help="scope di registrazione del server MCP in Claude Code (default: user)",
    )
    p.add_argument(
        "--browser-driver", choices=["extension", "playwright", "fake"], default="extension",
        help="driver browser scritto nel .env (default: extension)",
    )
    args = p.parse_args(argv)
    return check() if args.check else install(args)


if __name__ == "__main__":
    raise SystemExit(main())
