from pathlib import Path

import pytest

from autojob.browser.drivers.playwright_driver import PlaywrightDriver
from autojob.core import profile_service, ranking_service, search_service
from autojob.db.models.portals import Portal
from autojob.db.session import get_session
from autojob.utils.rate_limit import RateLimiter
from tests.fakes import FakeEmb, FakeLLM

pytestmark = pytest.mark.browser

RESULTS = (Path(__file__).parent / "fixtures" / "results.html").as_uri()


def _seed_test_portal():
    with get_session() as s:
        s.add(Portal(
            slug="testportal", name="Test Portal", base_url="file://",
            search_url_template=RESULTS, automation_policy="auto",
            requires_account=False, tos_risk="low", enabled=True,
        ))


async def test_search_jobs_on_portal_real(temp_db):
    _seed_test_portal()
    drv = PlaywrightDriver(headless=True)
    await drv.start()
    try:
        res = await search_service.search_jobs_on_portal(
            "testportal", {"keywords": "ai architect"}, max=5,
            driver=drv, rate=RateLimiter(0, 0), client=FakeLLM(None),
        )
        assert res["ok"] and res["found"] >= 2
        assert len(res["job_ids"]) >= 2
    finally:
        await drv.close()


async def test_run_search_end_to_end_and_authorize(temp_db):
    _seed_test_portal()
    profile_service.update_profile({"full_name": "Andrea", "headline": "AI Architect"})
    drv = PlaywrightDriver(headless=True)
    await drv.start()
    try:
        out = await search_service.run_search(
            {"keywords": "ai"}, portals=["testportal"], max_per_portal=5,
            driver=drv, rate=RateLimiter(0, 0), emb_client=FakeEmb(), client=FakeLLM(None),
        )
        assert out["search_run_id"] and out["found"] >= 2
        assert out["top"], "ranking dovrebbe restituire match"
        match_id = out["top"][0]["match_id"]
    finally:
        await drv.close()

    r = ranking_service.set_match_authorized(match_id, True)
    assert r["ok"] and r["authorized"] is True
