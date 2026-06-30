from autojob.config.loader import load_portals_seed


def test_portals_seed_loads_and_is_valid():
    seed = load_portals_seed()
    assert len(seed) >= 8
    slugs = {p["slug"] for p in seed}
    assert {"linkedin", "greenhouse", "lever"} <= slugs

    for p in seed:
        assert p["automation_policy"] in {"auto", "semi", "manual", "read_only"}
        assert p["tos_risk"] in {"low", "med", "high", "extreme"}
        assert isinstance(p["requires_account"], bool)
