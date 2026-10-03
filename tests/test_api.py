"""P0 API smoke tests: every documented endpoint responds and fixtures are SYNTHETIC-labelled."""

from fastapi.testclient import TestClient

from atlas.api import create_app

client = TestClient(create_app())

GETS = [
    "/api/meta",
    "/api/search?q=x",
    "/api/entities/MONDO:0000001",
    "/api/entities/MONDO:0000001/connections",
    "/api/entities/MONDO:0000001/assets",
    "/api/entities/MONDO:0000001/collaborators",
    "/api/entities/MONDO:0000001/graph",
    "/api/entities/MONDO:0000001/gap",
    "/api/claims/CLAIM:syn-1",
    "/api/simulations/SIM:syn-1",
]
POSTS = ["/api/explain", "/api/actions", "/api/uploads"]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_all_stub_endpoints_serve_synthetic_fixtures():
    for path in GETS:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "SYNTHETIC" in r.json()["_synthetic"], path
    for path in POSTS:
        r = client.post(path, json={})
        assert r.status_code == 200, path
        assert "SYNTHETIC" in r.json()["_synthetic"], path


def test_upload_stub_is_quarantined():
    assert client.post("/api/uploads", json={}).json()["quarantined"] is True
