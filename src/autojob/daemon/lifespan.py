from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect

from ..config.settings import get_settings
from ..db.session import get_engine, ping, vec_version
from ..utils.logging import get_logger


@asynccontextmanager
async def base_lifespan(app: FastAPI):
    log = get_logger()
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)

    from .ext_token import get_token, token_path

    get_token()  # genera il token del bridge estensione (/ext) se assente

    status: dict = {
        "db_ok": False,
        "vec": None,
        "schema_ready": False,
        "driver": s.browser_driver,
        "errors": [],
    }
    try:
        get_engine()
        status["db_ok"] = ping()
        status["vec"] = vec_version()
    except Exception as e:  # noqa: BLE001
        status["errors"].append(f"db: {e}")
        log.error(f"Errore init DB: {e}")

    try:
        names = inspect(get_engine()).get_table_names()
        status["schema_ready"] = "user_profile" in names
    except Exception as e:  # noqa: BLE001
        status["errors"].append(f"schema: {e}")

    app.state.status = status
    log.info(
        "AutoJob daemon avviato | db_ok={} vec={} schema_ready={} driver={}".format(
            status["db_ok"], status["vec"], status["schema_ready"], status["driver"]
        )
    )
    log.info(f"Token estensione (bridge /ext): {token_path()}")
    if not status["schema_ready"]:
        log.warning("Schema non inizializzato: esegui 'uv run alembic upgrade head'.")

    from . import activity

    async def _idle_watch() -> None:
        while True:
            await asyncio.sleep(60)
            cur = get_settings()
            if activity.should_shutdown(
                activity.idle_seconds(),
                enabled=cur.idle_shutdown_enabled,
                minutes=cur.idle_shutdown_minutes,
            ):
                log.info(f"Inattività {cur.idle_shutdown_minutes}m: spengo LM Studio e il daemon")
                try:
                    from ..core.lmstudio import manager

                    await manager.shutdown()
                except Exception:  # noqa: BLE001
                    pass
                activity.trigger_shutdown()
                break

    watch_task = asyncio.create_task(_idle_watch())
    try:
        yield
    finally:
        watch_task.cancel()
        try:
            get_engine().dispose()
        except Exception:  # noqa: BLE001
            pass
        log.info("AutoJob daemon arrestato")
