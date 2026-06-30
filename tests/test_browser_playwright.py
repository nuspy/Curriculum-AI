from pathlib import Path

import pytest

from autojob.browser.drivers.playwright_driver import PlaywrightDriver
from autojob.browser.port import BrowserDriver
from autojob.core.form_service import analyze_form

pytestmark = pytest.mark.browser

FIXTURE = (Path(__file__).parent / "fixtures" / "form.html").as_uri()


def test_playwright_driver_satisfies_protocol():
    assert isinstance(PlaywrightDriver(headless=True), BrowserDriver)


async def test_playwright_snapshot_form_and_handoff():
    drv = PlaywrightDriver(headless=True)
    await drv.start()
    try:
        nav = await drv.navigate(FIXTURE)
        assert nav.ok

        snap = await drv.get_snapshot()
        labels = [(e.label or "") for e in snap.elements]
        assert any("Full name" in x for x in labels)
        assert any("Email" in x for x in labels)
        # select options captured
        sel = next(e for e in snap.elements if e.tag == "select")
        assert sel.options and any(o["value"] == "senior" for o in sel.options)

        fm = analyze_form(snap)
        assert fm["submit_index"] is not None
        assert fm["field_count"] >= 5

        # fill by index (CDP isTrusted via Playwright)
        name_el = next(e for e in snap.elements if (e.label or "") == "Full name")
        r = await drv.fill(name_el.index, "Andrea Taini")
        assert r.ok

        # "Apply" opens a new tab → handoff
        opener = next(e for e in snap.elements if (e.text or "").startswith("Open new tab"))
        before = [t.target_id for t in await drv.list_targets()]
        res = await drv.click(opener.index, expect_new_target=True)
        assert res.ok
        newt = res.opened_target or await drv.wait_for_new_target(since=before)
        assert newt is not None
        assert newt.target_id not in before
    finally:
        await drv.close()
