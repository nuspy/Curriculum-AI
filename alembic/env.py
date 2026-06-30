from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from autojob.config.settings import get_settings
from autojob.db import models  # noqa: F401  popola Base.metadata
from autojob.db.base import Base
from autojob.db.session import make_engine

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata

_settings = get_settings()
URL = _settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(URL)  # il connect-hook carica sqlite-vec (serve per le tabelle vec0)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
