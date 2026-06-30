from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import sqlite_vec
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config.settings import get_settings
from .base import Base  # noqa: F401  (riesportato per comodità)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _on_connect(dbapi_conn, _record) -> None:
    """Hook su ogni connessione SQLite: carica sqlite-vec e imposta i PRAGMA."""
    dbapi_conn.enable_load_extension(True)
    sqlite_vec.load(dbapi_conn)
    dbapi_conn.enable_load_extension(False)
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.close()


def make_engine(url: str) -> Engine:
    engine = create_engine(url, future=True)
    event.listen(engine, "connect", _on_connect)
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        s.db_file.parent.mkdir(parents=True, exist_ok=True)
        _engine = make_engine(s.database_url)
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """Sessione transazionale: commit a uscita pulita, rollback su eccezione."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Per i test: chiude e azzera engine/sessionmaker così da rileggere i settings."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def ping() -> bool:
    with get_engine().connect() as conn:
        conn.execute(text("select 1"))
    return True


def vec_version() -> str | None:
    with get_engine().connect() as conn:
        return conn.execute(text("select vec_version()")).scalar()
