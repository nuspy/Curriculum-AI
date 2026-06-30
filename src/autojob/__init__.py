"""AutoJob — sistema locale modulare per cercare, valutare e compilare candidature.

Daemon locale (FastAPI) = unica fonte di verità; espone MCP (Streamable HTTP),
WebSocket per l'estensione browser, e una dashboard. La logica vive nei
``core/*_service.py``; i tool MCP sono wrapper sottili; il controllo browser è
dietro la porta ``browser.port.BrowserDriver`` con implementazioni intercambiabili.
"""

__version__ = "0.0.1"
