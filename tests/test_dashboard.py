from fastapi.testclient import TestClient

from autojob.core import intervention_service, profile_service
from autojob.core.extract_service import upsert_job_posting
from autojob.core.ranking_service import list_job_matches
from autojob.daemon.app import create_app
from autojob.db.models.jobs import JobMatch
from autojob.db.session import get_session


def _seed_match() -> int:
    up = upsert_job_posting({"title": "AI Architect", "company": "ACME", "description_md": "d"})
    with get_session() as s:
        m = JobMatch(
            job_posting_id=up["job_id"], score_total=78.0, criticality="high",
            success_probability=0.62, status="new", reasons=["forte overlap"],
        )
        s.add(m)
        s.flush()
        return m.id


def test_cockpit_home_and_matches_and_authorize(temp_db):
    _seed_match()
    with TestClient(create_app()) as client:
        assert "AutoJob" in client.get("/").text
        m = client.get("/ui/matches")
        assert m.status_code == 200 and "AI Architect" in m.text

        mid = list_job_matches()[0]["match_id"]
        a = client.post(f"/api/matches/{mid}/authorize", data={"authorized": "true"})
        assert a.status_code == 200

    assert list_job_matches()[0]["authorized"] is True


def test_cockpit_interventions_resolve(temp_db):
    iid = intervention_service.record_intervention(type="captcha", prompt="Risolvi il CAPTCHA")
    with TestClient(create_app()) as client:
        assert "Risolvi il CAPTCHA" in client.get("/ui/interventions").text
        rr = client.post(f"/api/interventions/{iid}/resolve")
        assert rr.status_code == 200 and "Risolvi il CAPTCHA" not in rr.text


def test_cockpit_profile_shows_provenance(temp_db):
    profile_service.update_profile({"full_name": "Andrea Taini"})
    with TestClient(create_app()) as client:
        r = client.get("/ui/profile")
        assert r.status_code == 200
        assert "Andrea Taini" in r.text
        assert "declared" in r.text  # badge provenance
