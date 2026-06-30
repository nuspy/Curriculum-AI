from pathlib import Path

import pytest

from autojob.browser.drivers.playwright_driver import PlaywrightDriver
from autojob.core import apply_service

pytestmark = pytest.mark.browser

FIXTURE = (Path(__file__).parent / "fixtures" / "form.html").as_uri()


async def test_add_repeating_section_real_chromium():
    drv = PlaywrightDriver(headless=True)
    await drv.start()
    try:
        await drv.navigate(FIXTURE)
        res = await apply_service.add_repeating_section("experience", driver=drv)
        assert res["ok"] and res["added"]
        assert res["field_count_after"] > res["field_count_before"]
        assert any("exp-" in (g or "") for g in res["new_group_ids"])
    finally:
        await drv.close()
