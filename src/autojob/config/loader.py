from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .settings import REPO_ROOT, get_settings

PORTALS_SEED = REPO_ROOT / "config" / "portals.seed.yaml"


def load_portals_seed(path: Path | None = None) -> list[dict[str, Any]]:
    """Carica le righe seed del registro portali da YAML."""
    p = path or PORTALS_SEED
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"portals seed deve essere una lista YAML, trovato {type(data)!r}")
    return data


__all__ = ["get_settings", "load_portals_seed", "PORTALS_SEED"]
