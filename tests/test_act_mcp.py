from fastmcp import Client

from autojob.core import browser_session
from autojob.mcp.server import build_mcp


def _data(r):
    d = getattr(r, "data", None)
    return d if d is not None else getattr(r, "structured_content", None)


async def test_act_tools_registered_and_callable(temp_db, monkeypatch):
    monkeypatch.setenv("AUTOJOB_BROWSER_DRIVER", "fake")
    from autojob.config import settings as sm

    sm.get_settings.cache_clear()
    await browser_session.reset_session_driver()

    mcp = build_mcp()
    try:
        async with Client(mcp) as c:
            names = {t.name for t in await c.list_tools()}
            assert {
                "fill_form_field", "click_element", "select_option", "set_checkbox",
                "upload_file", "scroll", "wait_for_dom_change", "verify_field",
                "detect_captcha", "map_profile_to_form", "fill_application",
                "submit_application", "add_repeating_section", "request_user_intervention",
                "switch_target",
            } <= names

            assert _data(await c.call_tool("detect_captcha", {}))["present"] is False

            # Apply button (index 0) sulla pagina fake
            assert _data(await c.call_tool("click_element", {"index": 0}))["ok"] is True

            plans = _data(await c.call_tool("map_profile_to_form", {}))
            assert isinstance(plans, list)
    finally:
        await browser_session.reset_session_driver()
