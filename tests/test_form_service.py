from autojob.browser.snapshot import ElementNode, PageSnapshot
from autojob.core.form_service import analyze_form


def _snap() -> PageSnapshot:
    els = [
        ElementNode(index=0, role="textbox", tag="input", type="text", label="Full name",
                    required=True, group_id="main"),
        ElementNode(index=1, role="combobox", tag="select", label="Seniority",
                    options=[{"value": "mid", "label": "Mid"}], group_id="main"),
        ElementNode(index=2, role="checkbox", tag="input", type="checkbox", label="I agree",
                    required=True, group_id="main"),
        ElementNode(index=3, role="button", tag="button", text="Add experience",
                    label="Add experience", group_id="main"),
        ElementNode(index=4, role="button", tag="button", text="Next", label="Next", group_id="main"),
        ElementNode(index=5, role="button", tag="button", text="Submit application",
                    label="Submit application", group_id="main"),
    ]
    return PageSnapshot(snapshot_id="s1", url="http://x", title="Apply", elements=els)


def test_analyze_form_classifies_fields_and_buttons():
    fm = analyze_form(_snap())
    assert fm["field_count"] == 3
    assert fm["submit_index"] == 5
    assert 4 in fm["next_indexes"]
    assert 3 in fm["add_indexes"]
    assert "main" in fm["groups"]
