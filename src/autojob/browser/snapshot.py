"""Rappresentazione normalizzata e indicizzata della pagina (piano §2).

L'agente agisce **per indice** (``ElementNode.index``), non per selettore CSS.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class ElementNode:
    index: int
    handle: str = ""
    role: str = ""
    tag: str = ""
    type: str | None = None
    label: str | None = None
    text: str | None = None
    value: str | None = None
    placeholder: str | None = None
    options: list[dict] | None = None
    checked: bool | None = None
    required: bool = False
    enabled: bool = True
    visible: bool = True
    focused: bool = False
    in_viewport: bool = False
    bbox: dict | None = None
    autocomplete: str | None = None
    group_id: str | None = None
    frame_path: list[str] = field(default_factory=list)
    attrs: dict = field(default_factory=dict)


@dataclass
class PageSnapshot:
    snapshot_id: str
    url: str = ""
    title: str = ""
    captured_at: str = ""
    viewport: dict = field(default_factory=dict)
    dom_hash: str = ""
    elements: list[ElementNode] = field(default_factory=list)
    forms: list[dict] = field(default_factory=list)
    frames: list[dict] = field(default_factory=list)
    has_captcha_hint: bool = False
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def by_index(self, index: int) -> ElementNode | None:
        for el in self.elements:
            if el.index == index:
                return el
        return None


_EL_FIELDS = {f.name for f in fields(ElementNode)}


def element_from_dict(d: dict) -> ElementNode:
    """Costruisce un ElementNode da un dict (snapshot ricevuto da driver/estensione)."""
    return ElementNode(**{k: v for k, v in d.items() if k in _EL_FIELDS})
