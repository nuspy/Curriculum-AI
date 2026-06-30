"""Driver browser deterministico in-memory per i test (nessun browser reale).

Simula una pagina "lista annunci" con un bottone Apply che apre il form di
candidatura in un **nuovo tab** (handoff multi-target, piano §9).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..port import ActionResult, CaptchaInfo, DomChange, TargetInfo
from ..snapshot import ElementNode, PageSnapshot


def _listing_snapshot(sid: str) -> PageSnapshot:
    return PageSnapshot(
        snapshot_id=sid,
        url="https://jobs.example.com/role/ai-architect",
        title="AI Architect — Example",
        captured_at="2026-01-01T00:00:00Z",
        dom_hash="listing-v1",
        elements=[
            ElementNode(index=0, role="button", tag="button", text="Apply", label="Apply",
                        handle="apply-btn"),
            ElementNode(index=1, role="link", tag="a", text="Company site", handle="co-link"),
        ],
    )


def _form_snapshot(sid: str) -> PageSnapshot:
    return PageSnapshot(
        snapshot_id=sid,
        url="https://ats.example.com/apply/123",
        title="Application form",
        captured_at="2026-01-01T00:00:05Z",
        dom_hash=f"form-{sid}",
        elements=[
            ElementNode(index=0, role="textbox", tag="input", type="text", label="Full name",
                        handle="f-name", required=True),
            ElementNode(index=1, role="textbox", tag="input", type="email", label="Email",
                        handle="f-email", required=True),
            ElementNode(index=2, role="textbox", tag="textarea", label="Cover letter",
                        handle="f-cover"),
            ElementNode(index=3, role="combobox", tag="select", label="Seniority", handle="f-sen",
                        options=[{"value": "mid", "label": "Mid", "selected": False},
                                 {"value": "senior", "label": "Senior", "selected": False}]),
            ElementNode(index=4, role="checkbox", tag="input", type="checkbox",
                        label="I agree to terms", handle="f-agree", required=True, checked=False),
            ElementNode(index=5, role="button", tag="input", type="file", label="Resume (PDF)",
                        handle="f-resume"),
            ElementNode(index=6, role="button", tag="button", text="Submit", label="Submit",
                        handle="f-submit"),
        ],
        forms=[{"group_id": "main", "action": "/apply/123", "method": "post",
                "field_indexes": [0, 1, 2, 3, 4, 5]}],
    )


class FakeDriver:
    name = "fake"

    def __init__(self) -> None:
        self._sid = 0
        listing = _listing_snapshot(self._next_sid())
        self._targets: dict[str, dict] = {
            "t1": {
                "info": TargetInfo("t1", "tab", listing.url, listing.title, active=True),
                "snapshot": listing,
            }
        }
        self._current = "t1"

    def _next_sid(self) -> str:
        self._sid += 1
        return f"snap-{self._sid}"

    def _cur(self) -> dict:
        return self._targets[self._current]

    async def attach(self, target: str | None = None) -> str:
        if target and target in self._targets:
            self._current = target
        return self._current

    async def navigate(self, url: str, *, wait: bool = True) -> ActionResult:
        snap = _listing_snapshot(self._next_sid())
        snap.url = url
        self._cur()["snapshot"] = snap
        return ActionResult(ok=True, new_snapshot_id=snap.snapshot_id, dom_changed=True)

    async def current_url(self) -> str:
        return self._cur()["snapshot"].url

    # --- tabs/windows ---
    async def list_targets(self) -> list[TargetInfo]:
        return [t["info"] for t in self._targets.values()]

    async def current_target(self) -> str:
        return self._current

    async def switch_target(self, target_id: str) -> ActionResult:
        if target_id not in self._targets:
            return ActionResult(ok=False, error_kind="not_found", message=f"target {target_id} assente")
        for tid, t in self._targets.items():
            t["info"].active = tid == target_id
        self._current = target_id
        return ActionResult(ok=True, message=f"switched->{target_id}")

    async def wait_for_new_target(
        self, *, since: Sequence[str] | None = None, timeout_ms: int = 8000
    ) -> TargetInfo | None:
        known = set(since or [])
        for tid in reversed(list(self._targets.keys())):
            if tid not in known:
                return self._targets[tid]["info"]
        return None

    async def close_target(self, target_id: str) -> ActionResult:
        if target_id in self._targets and target_id != "t1":
            self._targets.pop(target_id)
            if self._current == target_id:
                self._current = "t1"
            return ActionResult(ok=True)
        return ActionResult(ok=False, error_kind="not_found")

    # --- read ---
    async def get_snapshot(self, *, viewport_only: bool = False, include_hidden: bool = False) -> PageSnapshot:
        return self._cur()["snapshot"]

    async def get_page_text(self) -> str:
        snap = self._cur()["snapshot"]
        parts = [snap.title] + [(e.text or e.label or "") for e in snap.elements]
        return "\n".join(p for p in parts if p)

    async def screenshot(self, *, full_page: bool = False) -> bytes:
        return b"\x89PNG\r\n\x1a\n"

    # --- act ---
    async def click(self, index: int, *, expect_new_target: bool = False) -> ActionResult:
        el = self._cur()["snapshot"].by_index(index)
        if el is None:
            return ActionResult(ok=False, index=index, error_kind="not_found")
        if el.handle == "apply-btn":
            tid = f"t{len(self._targets) + 1}"
            form = _form_snapshot(self._next_sid())
            info = TargetInfo(tid, "tab", form.url, form.title, active=False, opener_id=self._current)
            self._targets[tid] = {"info": info, "snapshot": form}
            return ActionResult(ok=True, index=index, dom_changed=True, opened_target=info,
                                message="opened application tab")
        return ActionResult(ok=True, index=index, dom_changed=(el.handle == "f-submit"),
                            message="clicked")

    async def fill(self, index: int, value: str, *, trusted: bool = True, clear: bool = True) -> ActionResult:
        el = self._cur()["snapshot"].by_index(index)
        if el is None:
            return ActionResult(ok=False, index=index, error_kind="not_found")
        el.value = value
        return ActionResult(ok=True, index=index, value_after=value, dom_changed=True)

    async def select_option(self, index: int, *, value: str | None = None, label: str | None = None) -> ActionResult:
        el = self._cur()["snapshot"].by_index(index)
        if el is None or not el.options:
            return ActionResult(ok=False, index=index, error_kind="not_found")
        chosen = None
        for opt in el.options:
            opt["selected"] = opt.get("value") == value or opt.get("label") == label
            if opt["selected"]:
                chosen = opt.get("value")
        el.value = chosen
        return ActionResult(ok=chosen is not None, index=index, value_after=chosen)

    async def set_checkbox(self, index: int, checked: bool) -> ActionResult:
        el = self._cur()["snapshot"].by_index(index)
        if el is None:
            return ActionResult(ok=False, index=index, error_kind="not_found")
        el.checked = checked
        return ActionResult(ok=True, index=index, value_after=str(checked))

    async def upload_file(self, index: int, paths: Sequence[str]) -> ActionResult:
        el = self._cur()["snapshot"].by_index(index)
        if el is None:
            return ActionResult(ok=False, index=index, error_kind="not_found")
        el.value = ";".join(paths)
        return ActionResult(ok=True, index=index, value_after=el.value)

    async def scroll(self, *, to_index: int | None = None, dy: int = 0, dx: int = 0) -> ActionResult:
        return ActionResult(ok=True, index=to_index)

    async def press_key(self, index: int | None, key: str) -> ActionResult:
        return ActionResult(ok=True, index=index, message=f"key:{key}")

    # --- wait / verify / escape ---
    async def wait_for_dom_change(self, *, timeout_ms: int = 8000, expect_url_change: bool = False) -> DomChange:
        snap = self._cur()["snapshot"]
        return DomChange(changed=True, mutations=1, url_changed=expect_url_change,
                         new_snapshot_id=snap.snapshot_id)

    async def eval_js(self, expr: str, *, world: str = "ISOLATED") -> object:
        return None

    async def detect_captcha(self) -> CaptchaInfo | None:
        return None

    async def close(self) -> None:
        return None
