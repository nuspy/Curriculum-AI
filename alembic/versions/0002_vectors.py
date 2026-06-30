"""vectors (tabelle virtuali vec0 di sqlite-vec)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30
"""
from collections.abc import Sequence

from alembic import op
from autojob.config.settings import get_settings
from autojob.db.schema import vec_ddl, vec_drop_ddl

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dim = get_settings().embed_dim
    for stmt in vec_ddl(dim):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in vec_drop_ddl():
        op.execute(stmt)
