"""Token condiviso per autenticare l'estensione sul bridge WS (piano §3)."""

from __future__ import annotations

import uuid
from pathlib import Path

from ..config.settings import get_settings


def token_path() -> Path:
    return get_settings().data_dir / "ext_token"


def get_token() -> str:
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        tok = p.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    tok = uuid.uuid4().hex
    p.write_text(tok, encoding="utf-8")
    return tok
