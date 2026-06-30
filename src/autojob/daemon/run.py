from __future__ import annotations

import uvicorn

from ..config.settings import get_settings


def main() -> None:
    s = get_settings()
    config = uvicorn.Config(
        "autojob.daemon.app:create_app",
        factory=True,
        host=s.host,
        port=s.port,
        log_level=s.log_level.lower(),
    )
    server = uvicorn.Server(config)
    # Permette all'idle-watchdog di arrestare il daemon.
    from .activity import set_shutdown_hook

    set_shutdown_hook(lambda: setattr(server, "should_exit", True))
    server.run()


if __name__ == "__main__":
    main()
