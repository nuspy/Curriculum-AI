from sqlalchemy import select

from autojob.core import cv_ingest_service, extract_service, profile_service, ranking_service
from autojob.db.models.provenance import FieldProvenance
from autojob.db.session import get_session
from tests.fakes import FakeEmb, FakeLLM

CV_RAW = (
    "Andrea Taini\nAI Architect\nEmail: a@b.com\n"
    "Skills: Python, MCP, FastAPI\n"
    "Experience: Lead AI Engineer at ACME (2022-now)\n"
)
CV_JSON = {
    "personal_info": {"full_name": "Andrea Taini", "headline": "AI Architect", "email": "a@b.com"},
    "skills": [{"name": "Python"}, {"name": "MCP"}, {"name": "FastAPI"}],
    "work_experience": [{"company": "ACME", "title": "Lead AI Engineer", "start_date": "2022"}],
}


async def test_normalize_cv_writes_profile_with_provenance(temp_db):
    res = await cv_ingest_service.normalize_cv(raw_md=CV_RAW, client=FakeLLM(CV_JSON))
    assert res["ok"] is True
    assert res["counts"]["skills"] == 3
    assert set(res["gaps"]) >= {"phone", "location"}

    prof = profile_service.get_profile()
    assert prof["profile"]["full_name"] == "Andrea Taini"
    assert len(prof["skills"]) == 3

    with get_session() as s:
        fp = s.execute(
            select(FieldProvenance).where(
                FieldProvenance.table_name == "user_profile",
                FieldProvenance.column_name == "full_name",
            )
        ).scalar_one()
        assert fp.provenance == "certain"  # "Andrea Taini" è presente nel testo


async def test_extract_job_posting_and_dedup(temp_db):
    job_json = {
        "title": "AI Architect", "company": "ACME", "location": "Remote",
        "tech_tags": ["Python", "MCP"], "seniority": "senior",
        "salary_min": 90000, "salary_currency": "EUR",
    }
    res = await extract_service.extract_job_posting(
        pasted_text="AI Architect at ACME, remote, Python/MCP",
        client=FakeLLM(job_json),
    )
    assert res["ok"] and res["job_id"]
    assert res["is_new"] is True
    assert res["applied"]["state"] == "none"

    # Stesso annuncio → dedup (non crea nuovo)
    res2 = await extract_service.extract_job_posting(
        pasted_text="AI Architect at ACME, remote, Python/MCP",
        client=FakeLLM(job_json),
    )
    assert res2["job_id"] == res["job_id"]
    assert res2["is_new"] is False


async def test_rank_jobs_end_to_end(temp_db):
    profile_service.update_profile({"full_name": "Andrea", "headline": "AI Architect"})
    profile_service.update_preferences(
        {"job_titles": ["AI Architect"], "seniority_target": "senior",
         "salary_min": 80000, "remote_pref": "remote"}
    )
    await cv_ingest_service.normalize_cv(raw_md=CV_RAW, client=FakeLLM(CV_JSON))
    await extract_service.extract_job_posting(
        pasted_text="AI Architect at ACME",
        client=FakeLLM({
            "title": "AI Architect", "company": "ACME", "location": "Remote",
            "remote_type": "remote", "seniority": "senior", "salary_min": 90000,
            "tech_tags": ["Python", "MCP"], "description_md": "x" * 300,
        }),
    )
    ranked = await ranking_service.rank_jobs(emb_client=FakeEmb())
    assert ranked
    top = ranked[0]
    assert 0 <= top["score_total"] <= 100
    assert "tech_overlap" in top["score_breakdown"]
    assert top["match_id"]

    listed = ranking_service.list_job_matches()
    assert listed and listed[0]["job_id"] == top["job_id"]
