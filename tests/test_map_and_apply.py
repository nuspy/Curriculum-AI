from sqlalchemy import func, select

from autojob.browser.drivers.fake_driver import FakeDriver
from autojob.browser.snapshot import ElementNode, PageSnapshot
from autojob.core import apply_service, extract_service, intervention_service, profile_service
from autojob.core.form_service import analyze_form, map_profile_to_form
from autojob.db.models.browser import ActionLog
from autojob.db.session import get_session


def _form_snapshot() -> PageSnapshot:
    els = [
        ElementNode(index=0, role="textbox", tag="input", type="text", label="Full name",
                    required=True, attrs={"name": "name"}),
        ElementNode(index=1, role="textbox", tag="input", type="email", label="Email",
                    required=True, attrs={"name": "email"}),
        ElementNode(index=2, role="checkbox", tag="input", type="checkbox",
                    label="I agree to terms", required=True, attrs={"name": "agree"}),
        ElementNode(index=3, role="file", tag="input", type="file", label="Resume",
                    attrs={"name": "cv"}),
        ElementNode(index=4, role="textbox", tag="input", type="text", label="Company name",
                    required=True, attrs={"name": "company"}),
        ElementNode(index=5, role="button", tag="button", text="Submit application"),
    ]
    return PageSnapshot(snapshot_id="s", url="http://x", title="Apply", elements=els)


def test_map_profile_to_form():
    fm = analyze_form(_form_snapshot())
    profile = {"profile": {"full_name": "Andrea Taini", "email": "a@b.com"}, "preferences": {}}
    plans = {p["label"]: p for p in map_profile_to_form(fm, profile, cv_path="C:/cv.pdf")}

    assert plans["Full name"]["action"] == "fill" and plans["Full name"]["value"] == "Andrea Taini"
    assert plans["Email"]["source"] == "profile.email"
    assert plans["I agree to terms"]["action"] == "check" and plans["I agree to terms"]["value"] is True
    assert plans["Resume"]["action"] == "upload" and "cv.pdf" in plans["Resume"]["value"]
    # campo obbligatorio senza mapping → needs_user (mai inventato)
    assert plans["Company name"]["needs_user"] is True


async def test_fill_application_fake_driver(temp_db):
    profile_service.update_profile({"full_name": "Andrea Taini", "email": "a@b.com"})
    up = extract_service.upsert_job_posting({"title": "AI Architect", "company": "ACME", "description_md": "d"})
    job_id = up["job_id"]

    d = FakeDriver()
    await d.attach()
    listing = await d.get_snapshot()
    apply_btn = next(e for e in listing.elements if e.label == "Apply")
    res = await d.click(apply_btn.index, expect_new_target=True)
    await d.switch_target(res.opened_target.target_id)  # passa al form

    report = await apply_service.fill_application(job_id, driver=d)
    assert report["ok"] and report["status"] == "ready_for_review"
    assert report["mode"] == "manual" and report["submitted"] is False
    labels = {f["label"] for f in report["filled"]}
    assert {"Full name", "Email"} <= labels
    assert all(v["ok"] for v in report["verify"])

    with get_session() as s:
        n = s.execute(select(func.count()).select_from(ActionLog)).scalar()
    assert n >= 2


def test_intervention_record_and_resolve(temp_db):
    iid = intervention_service.record_intervention(type="captcha", prompt="Solve the CAPTCHA")
    assert any(p["id"] == iid for p in intervention_service.list_pending())
    assert intervention_service.resolve_intervention(iid, response={"text": "done"})
    assert all(p["id"] != iid for p in intervention_service.list_pending())
