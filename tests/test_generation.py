from autojob.core import extract_service, generation_service
from tests.fakes import FakeLLM


async def _make_job(temp_db):
    res = await extract_service.extract_job_posting(
        pasted_text="AI Architect at ACME",
        client=FakeLLM({"title": "AI Architect", "company": "ACME", "description_md": "d"}),
    )
    return res["job_id"]


async def test_cover_letter_local(temp_db):
    jid = await _make_job(temp_db)
    res = await generation_service.generate_cover_letter(
        jid, client=FakeLLM(text="Dear ACME, ...")
    )
    assert res["ok"] and res["mode"] == "local"
    assert "ACME" in res["text"]


async def test_cover_letter_agent_delegate(temp_db):
    jid = await _make_job(temp_db)
    res = await generation_service.generate_cover_letter(jid, target="agent")
    assert res["ok"] and res["mode"] == "delegate"
    assert "prompt" in res and "system" in res


async def test_form_answer_needs_user(temp_db):
    jid = await _make_job(temp_db)
    res = await generation_service.generate_form_answer(
        "What is your expected salary?", jid,
        client=FakeLLM(text="NEED_USER: expected salary not in profile"),
    )
    assert res["ok"] and res.get("needs_user") is True


async def test_form_answer_generated(temp_db):
    jid = await _make_job(temp_db)
    res = await generation_service.generate_form_answer(
        "Why this role?", jid, client=FakeLLM(text="Because I build AI agents.")
    )
    assert res["ok"] and res["source"] == "generated"
    assert "AI agents" in res["answer"]
