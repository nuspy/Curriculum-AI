from fastmcp import Client

from autojob.core import browser_session
from autojob.mcp.server import build_mcp


def _data(r):
    d = getattr(r, "data", None)
    return d if d is not None else getattr(r, "structured_content", None)


async def test_browser_mcp_tools_with_fake_driver(temp_db, monkeypatch):
    monkeypatch.setenv("AUTOJOB_BROWSER_DRIVER", "fake")
    from autojob.config import settings as sm

    sm.get_settings.cache_clear()
    await browser_session.reset_session_driver()

    mcp = build_mcp()
    try:
        async with Client(mcp) as c:
            names = {t.name for t in await c.list_tools()}
            assert {"navigate", "get_page_snapshot", "analyze_form", "list_targets"} <= names

            snap = _data(await c.call_tool("get_page_snapshot", {}))
            assert "elements" in snap and snap["title"]
            assert "db_id" in snap  # persistito in page_snapshots

            fm = _data(await c.call_tool("analyze_form", {}))
            assert "fields" in fm and "buttons" in fm

            targets = _data(await c.call_tool("list_targets", {}))
            assert isinstance(targets, list) and targets
    finally:
        await browser_session.reset_session_driver()
