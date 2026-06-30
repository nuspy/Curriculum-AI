from fastmcp import Client

from autojob.mcp.server import build_mcp


def _data(result):
    d = getattr(result, "data", None)
    if d is not None:
        return d
    return getattr(result, "structured_content", None)


async def test_mcp_tools_registered_and_callable(temp_db):
    mcp = build_mcp()
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
        assert {
            "get_user_profile",
            "update_user_profile",
            "parse_cv",
            "normalize_cv",
            "extract_job_posting",
            "rank_job_matches",
            "list_job_matches",
            "generate_cover_letter",
            "generate_form_answer",
            "check_application_status",
            "save_application_status",
        } <= names

        prof = _data(await c.call_tool("get_user_profile", {}))
        assert "profile" in prof

        applied = _data(await c.call_tool(
            "check_application_status",
            {"job_identity": {"title": "X", "company": "Y", "location": "Z", "description": "d"}},
        ))
        assert applied["state"] == "none"
