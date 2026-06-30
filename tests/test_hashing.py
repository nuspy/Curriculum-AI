from autojob.utils.hashing import (
    canonical_job_key,
    content_hash,
    job_fingerprint,
    normalize_apply_url,
    normalize_question,
)


def test_normalize_apply_url_strips_tracking_and_fragment():
    out = normalize_apply_url("https://WWW.Example.com/jobs/123/?utm_source=x&ref=y&id=5#frag")
    assert out == "https://example.com/jobs/123?id=5"


def test_normalize_apply_url_query_order_independent():
    assert normalize_apply_url("https://x.com/a?b=2&a=1") == normalize_apply_url("https://x.com/a?a=1&b=2")


def test_content_hash_normalizes_input():
    h1 = content_hash(title="AI Architect", company="ACME", location="Remote")
    h2 = content_hash(title="ai  architect", company="acme", location="remote")
    assert h1 == h2


def test_canonical_key_prefers_external_id():
    k1 = canonical_job_key(portal_slug="linkedin", external_id="123")
    k2 = canonical_job_key(portal_slug="linkedin", external_id="123")
    assert k1 == k2
    assert canonical_job_key(apply_url="https://a.com/x") != k1


def test_fingerprint_and_question_normalization():
    assert job_fingerprint("ACME", "AI Architect", "Budapest") == job_fingerprint(
        "acme", "ai architect", "budapest"
    )
    assert normalize_question("  Why do you want this JOB?? ") == "why do you want this job"
