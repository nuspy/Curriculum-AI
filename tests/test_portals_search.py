from fastmcp import Client

from autojob.browser.snapshot import ElementNode, PageSnapshot
from autojob.core import portal_service
from autojob.core.search_service import extract_result_links
from autojob.mcp.server import build_mcp


def _data(r):
    d = getattr(r, "data", None)
    return d if d is not None else getattr(r, "structured_content", None)


def test_seed_and_filter_portals(temp_db):
    res = portal_service.seed_portals()
    assert res["seeded"] >= 8

    slugs = {p["slug"] for p in portal_service.list_portals()}
    assert {"linkedin", "greenhouse"} <= slugs

    low = portal_service.list_portals({"max_tos_risk": "low"})
    assert all(p["tos_risk"] == "low" for p in low)
    assert "linkedin" not in {p["slug"] for p in low}  # extreme escluso

    searchable = portal_service.list_portals({"searchable_only": True})
    assert all(p["search_url_template"] for p in searchable)
    assert "greenhouse" not in {p["slug"] for p in searchable}  # template vuoto (ATS)


def test_extract_result_links_heuristic():
    els = [
        ElementNode(index=0, role="link", tag="a", text="Job A", attrs={"href": "https://x.com/jobs/123"}),
        ElementNode(index=1, role="link", tag="a", text="About", attrs={"href": "https://x.com/about"}),
        ElementNode(index=2, role="link", tag="a", text="Job B", attrs={"href": "https://x.com/job-456"}),
    ]
    links = extract_result_links(PageSnapshot(snapshot_id="s", elements=els))
    assert "https://x.com/jobs/123" in links
    assert "https://x.com/job-456" in links
    assert "https://x.com/about" not in links


async def test_search_mcp_tools_registered(temp_db):
    mcp = build_mcp()
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
        assert {
            "seed_portals", "search_job_portals", "search_jobs_on_portal",
            "run_search", "authorize_match",
        } <= names

        assert _data(await c.call_tool("seed_portals", {}))["seeded"] >= 8
        portals = _data(await c.call_tool("search_job_portals", {"max_tos_risk": "low"}))
        assert isinstance(portals, list) and all(p["tos_risk"] == "low" for p in portals)
