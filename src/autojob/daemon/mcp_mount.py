from __future__ import annotations

from ..mcp.server import build_mcp


def get_mcp_app():
    """ASGI app MCP (Streamable HTTP). Montata su ``/mcp`` → endpoint a ``/mcp/``."""
    return build_mcp().http_app(path="/")
