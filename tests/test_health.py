from fastapi.testclient import TestClient

from autojob.daemon.app import create_app


def test_health_and_ready(temp_db):
    with TestClient(create_app()) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        rr = client.get("/ready")
        assert rr.status_code == 200
        body = rr.json()
        assert body["ready"] is True
        assert body["components"]["db"] == "ok"
        assert body["components"]["sqlite_vec"]
        assert body["components"]["schema"] == "ok"
