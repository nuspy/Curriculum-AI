from __future__ import annotations

import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """DB SQLite temporaneo con schema completo (tabelle ORM + vec0)."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("AUTOJOB_DB_PATH", str(db))
    monkeypatch.setenv("AUTOJOB_DATA_DIR", str(tmp_path))

    from autojob.config import settings as settings_mod
    from autojob.db import session as session_mod

    settings_mod.get_settings.cache_clear()
    session_mod.reset_engine()

    from autojob.db.schema import create_all_schema

    create_all_schema()
    yield db

    session_mod.reset_engine()
    settings_mod.get_settings.cache_clear()
