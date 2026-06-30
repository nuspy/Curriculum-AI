"""Creazione schema completo (tabelle ORM + tabelle virtuali vec0).

La DDL vec0 vive QUI ed è riusata sia dalla migrazione Alembic 0002 sia da
``create_all_schema`` (usata nei test), per evitare drift.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..config.settings import get_settings
from . import models  # noqa: F401  popola Base.metadata
from .base import Base
from .session import get_engine

VEC_TABLES = ("job_postings_vec", "skills_vec", "approved_answers_vec")


def vec_ddl(dim: int) -> list[str]:
    return [
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {t} USING vec0(embedding float[{dim}]);"
        for t in VEC_TABLES
    ]


def vec_drop_ddl() -> list[str]:
    return [f"DROP TABLE IF EXISTS {t};" for t in VEC_TABLES]


def create_all_schema(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    dim = get_settings().embed_dim
    with engine.begin() as conn:
        for stmt in vec_ddl(dim):
            conn.execute(text(stmt))
