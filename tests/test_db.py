from sqlalchemy import select

from autojob.db.enums import Provenance
from autojob.db.models.profile import UserProfile
from autojob.db.models.provenance import FieldProvenance
from autojob.db.provenance import record_provenance
from autojob.db.session import get_session


def test_profile_and_provenance_roundtrip(temp_db):
    with get_session() as s:
        p = UserProfile(full_name="Andrea Taini", email="a@example.com", default_language="en")
        s.add(p)
        s.flush()
        pid = p.id
        record_provenance(
            s,
            table_name="user_profile",
            row_id=pid,
            column_name="full_name",
            provenance=Provenance.CERTAIN,
            source="Andrea_Taini_CV_2026.pdf",
        )

    with get_session() as s:
        got = s.get(UserProfile, pid)
        assert got is not None
        assert got.full_name == "Andrea Taini"
        assert got.created_at is not None  # server_default

        fp = s.execute(
            select(FieldProvenance).where(FieldProvenance.row_id == pid)
        ).scalar_one()
        assert fp.provenance == "certain"
        assert fp.source.endswith(".pdf")


def test_provenance_upsert_is_idempotent(temp_db):
    with get_session() as s:
        record_provenance(s, table_name="t", row_id=1, column_name="c",
                          provenance=Provenance.INFERRED)
        record_provenance(s, table_name="t", row_id=1, column_name="c",
                          provenance=Provenance.DECLARED)
    with get_session() as s:
        rows = s.execute(
            select(FieldProvenance).where(FieldProvenance.table_name == "t")
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].provenance == "declared"
