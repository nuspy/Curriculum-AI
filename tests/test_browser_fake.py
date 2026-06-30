from autojob.browser import get_driver
from autojob.browser.port import BrowserDriver


def _by_label(snap, label):
    return next(e for e in snap.elements if e.label == label)


async def test_fake_driver_satisfies_protocol():
    assert isinstance(get_driver("fake"), BrowserDriver)


async def test_multi_target_handoff_and_form_fill():
    d = get_driver("fake")
    await d.attach()

    listing = await d.get_snapshot()
    assert listing.title.startswith("AI Architect")
    apply_btn = _by_label(listing, "Apply")

    before = [t.target_id for t in await d.list_targets()]
    res = await d.click(apply_btn.index, expect_new_target=True)
    assert res.ok and res.opened_target is not None

    new_target = await d.wait_for_new_target(since=before)
    assert new_target is not None
    assert new_target.target_id not in before

    assert (await d.switch_target(new_target.target_id)).ok

    form = await d.get_snapshot()
    assert form.title == "Application form"

    r_name = await d.fill(_by_label(form, "Full name").index, "Andrea Taini")
    assert r_name.ok and r_name.value_after == "Andrea Taini"

    r_sel = await d.select_option(_by_label(form, "Seniority").index, value="senior")
    assert r_sel.ok and r_sel.value_after == "senior"

    assert (await d.set_checkbox(_by_label(form, "I agree to terms").index, True)).ok

    r_up = await d.upload_file(_by_label(form, "Resume (PDF)").index, ["C:/cv.pdf"])
    assert r_up.ok and "cv.pdf" in r_up.value_after


async def test_unknown_index_returns_not_found():
    d = get_driver("fake")
    res = await d.click(999)
    assert not res.ok and res.error_kind == "not_found"
