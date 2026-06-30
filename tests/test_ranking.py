from autojob.core.ranking_service import score_match


def test_score_match_strong_fit():
    job = {
        "title": "AI Architect", "company_name_raw": "ACME", "seniority": "senior",
        "salary_min": 100000, "remote_type": "remote",
        "tech_tags": ["python", "mcp"], "requirements": ["python"],
        "description_md": "x" * 400,
    }
    prof = {"skills": [{"name": "Python"}, {"name": "MCP"}], "profile": {}}
    prefs = {
        "job_titles": ["AI Architect"], "seniority_target": "senior",
        "salary_min": 80000, "remote_pref": "remote", "locations": [],
    }
    sc = score_match(job, prof, prefs, semantic_fit=0.8)
    assert 0 <= sc["score_total"] <= 100
    assert sc["score_breakdown"]["tech_overlap"] > 0.5
    assert sc["success_probability"] > 0.5
    assert sc["penalties"] == []


def test_score_match_penalties_applied():
    job = {
        "title": "Junior Dev", "seniority": "junior", "salary_min": 20000,
        "description_md": "short", "company_name_raw": None,
    }
    prefs = {"seniority_target": "senior", "salary_min": 80000}
    sc = score_match(job, {"skills": []}, prefs, semantic_fit=0.0)
    keys = {p["k"] for p in sc["penalties"]}
    assert {"too_junior", "underpaid", "unclear_company", "generic_posting"} <= keys
