"""P0 API smoke tests: every documented endpoint responds and fixtures are SYNTHETIC-labelled."""

from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.api.settings import Settings

# Fixture mode: the real-ontology search is tested in test_search.py without the large files.
client = TestClient(create_app(Settings(real_search=False)))

E = "/api/entities/SYN:disease-a"
GETS = [
    "/api/meta",
    "/api/search?q=disease",
    "/api/entities",
    E,
    f"{E}/connections",
    f"{E}/assets",
    f"{E}/collaborators",
    f"{E}/graph",
    f"{E}/gap",
    f"{E}/actions",
    "/api/claims/CLAIM:syn-1",
    "/api/simulations/SIM:syn-pass",
]
POSTS = ["/api/explain", "/api/actions"]


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


def test_unknown_ids_404():
    assert client.get("/api/entities/SYN:nope").status_code == 404
    assert client.get("/api/claims/CLAIM:nope").status_code == 404


def test_demo_dataset_validates_against_models():
    """The demo is built through the models; re-validate the served JSON (catches drift)."""
    from atlas.api.routes import _demo_cached
    from atlas.api.settings import Settings
    from atlas.schemas import (
        ActionCard,
        AssetResult,
        Claim,
        ConnectionResult,
        CoverageManifest,
        Entity,
        GapResult,
    )

    d = _demo_cached(Settings().fixtures_dir)
    for e in d["entities"]:
        assert Entity(**e).id.startswith("SYN:")
    for c in d["claims"]:
        Claim(**c)
    for m in d["manifests"]:
        CoverageManifest(**m)
    for rows, model in ((d["connections"], ConnectionResult), (d["assets"], AssetResult),
                        (d["cards"], ActionCard)):
        for items in rows.values():
            for x in items:
                model(**x)
    for g in d["gaps"].values():
        GapResult(**g)


def test_claim_lineage_and_contradictions():
    r = client.get("/api/claims/CLAIM:syn-14").json()
    assert "CLAIM:syn-23" in r["contradicting_claims"]
    r = client.get("/api/claims/CLAIM:syn-12").json()
    assert "CLAIM:syn-13" in r["lineage_siblings"]


def test_meta_featured_entries_are_derived_from_the_dataset():
    m = client.get("/api/meta").json()
    ids = {e["id"] for e in client.get("/api/entities").json()["items"]}
    assert m["featured"], "dataset has connections and gaps, so something is featured"
    for f in m["featured"]:
        assert f["id"] in ids
        assert f["reason"] in {"connections", "gap"}
    assert {s["run_id"] for s in m["simulations"]} == {"SIM:syn-pass", "SIM:syn-fail"}
