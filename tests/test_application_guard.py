from datetime import datetime, timezone

from autojob.core.application_service import check_application_status, save_application_status
from autojob.core.extract_service import upsert_job_posting
from autojob.db.enums import ApplicationStatus
from autojob.db.models.applications import Application
from autojob.db.session import get_session

IDENT = {
    "url": "https://acme.com/jobs/1",
    "title": "AI Architect",
    "company": "ACME",
    "location": "Remote",
    "description": "Build AI agents",
}


def test_duplicate_guard_none_then_submitted(temp_db):
    up = upsert_job_posting({
        "title": "AI Architect", "company": "ACME", "location": "Remote",
        "description_md": "Build AI agents",
        "url": "https://acme.com/jobs/1?utm_source=newsletter",
    })
    jid = up["job_id"]

    assert check_application_status(IDENT)["state"] == "none"

    with get_session() as s:
        s.add(Application(
            job_posting_id=jid,
            status=ApplicationStatus.SUBMITTED.value,
            submitted_at=datetime.now(timezone.utc),
        ))

    st = check_application_status(IDENT)
    assert st["state"] == "submitted"
    assert st["strength"] == "strong"
    assert st["details"]["job_posting_id"] == jid


def test_save_application_status_sets_submitted_at(temp_db):
    up = upsert_job_posting({"title": "Dev", "company": "X", "description_md": "d"})
    with get_session() as s:
        app = Application(job_posting_id=up["job_id"], status=ApplicationStatus.DRAFT.value)
        s.add(app)
        s.flush()
        app_id = app.id

    res = save_application_status(app_id, ApplicationStatus.SUBMITTED.value, {"mode": "manual"})
    assert res["ok"] and res["status"] == "submitted"
    with get_session() as s:
        assert s.get(Application, app_id).submitted_at is not None
