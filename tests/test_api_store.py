"""API reads of the persistent claim store. Claims are SYNTHETIC fixtures (software behaviour only)."""

import pytest
from fastapi.testclient import TestClient
from tests.conftest import make_claim

from atlas.api import create_app
from atlas.api.settings import Settings
from atlas.db import AtlasDB

A, B = "SYN:disease-a", "SYN:disease-b"
G = "HGNC:100"


@pytest.fixture()
def client(tmp_path):
    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    db.put(make_claim("CLAIM:one", "GENE_ASSOCIATED_WITH_DISEASE", subject_id=G, object_id=A))
    db.put(make_claim("CLAIM:two", "GENE_ASSOCIATED_WITH_DISEASE", subject_id=G, object_id=B))
    db.put(make_claim("CLAIM:inf", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=B, status="inference"))
    db.close()
    return TestClient(create_app(Settings(real_search=False, store_path=path)))


def test_graph_comes_from_stored_claims_with_a_claim_id_on_every_edge(client):
    body = client.get(f"/api/entities/{A}/graph").json()
    assert {e["claim_id"] for e in body["edges"]} == {"CLAIM:one", "CLAIM:two", "CLAIM:inf"}
    assert "unreviewed" in body["_synthetic"] and body["truncated"] is False
    assert all(e["claim_id"].startswith("CLAIM:") for e in body["edges"])


def test_routes_lists_observed_route_first_and_labels_the_hypothesis_only_one(client):
    body = client.get(f"/api/entities/{A}/routes", params={"to": B}).json()
    assert body["gap"] is None
    assert [p["hypothesis_only"] for p in body["paths"]] == [False, True]
    assert [n["id"] for n in body["paths"][0]["nodes"]] == [A, G, B]
    assert body["paths"][0]["hops"][0]["claim_ids"] == ["CLAIM:one"]


def test_routes_with_no_path_returns_a_scoped_gap_not_an_error(client):
    body = client.get(f"/api/entities/{A}/routes", params={"to": "MONDO:0009999"}).json()
    assert body["paths"] == [] and body["gap"]["kind"] == "no_supported_route"
    assert "indexed evidence as of" in body["gap"]["statement"]


def test_stored_claim_opens_in_the_evidence_drawer_route(client):
    body = client.get("/api/claims/CLAIM:one").json()
    assert body["claim"]["claim_id"] == "CLAIM:one" and "unreviewed" in body["_synthetic"]


def test_missing_store_means_no_claims_and_the_old_behaviour(tmp_path):
    c = TestClient(create_app(Settings(real_search=False, store_path=tmp_path / "none.db")))
    assert c.get(f"/api/entities/{A}/graph").status_code == 200
    assert c.get(f"/api/entities/{A}/routes", params={"to": B}).json()["gap"] is not None


def test_routes_requires_a_target_and_an_unknown_entity_is_404(client):
    assert client.get(f"/api/entities/{A}/routes").status_code == 422
    assert client.get("/api/entities/SYN:nope/routes", params={"to": B}).status_code == 404


def test_an_ai_hypothesis_opens_in_the_drawer_route_with_its_origin_fields(tmp_path):
    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    db.put(make_claim("CLAIM:one", "ACCUMULATES_IN_COMPARTMENT", subject_id=A, object_id="GO:0005764", source_type="published"))
    db.put(make_claim("CLAIM:two", "ACCUMULATES_IN_COMPARTMENT", subject_id=B, object_id="GO:0005764", source_type="published"))
    db.put(make_claim(
        "CLAIM:HYP-1", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=B, status="inference",
        source_type="ai_generated", source_url="atlas:ai-hypothesis", source_span="AI hypothesis: both accumulate in lysosome",
        derived_from=("CLAIM:one", "CLAIM:two"), extraction_method="llm:m@hypothesis-v1",
    ))
    db.close()
    c = TestClient(create_app(Settings(real_search=False, store_path=path)))
    claim = c.get("/api/claims/CLAIM:HYP-1").json()["claim"]
    assert claim["source_type"] == "ai_generated" and claim["derived_from"] == ["CLAIM:one", "CLAIM:two"]
    assert claim["review_state"] == "unreviewed" and claim["extraction_method"].startswith("llm:")


def test_drug_claims_can_be_hidden_by_policy_and_are_shown_otherwise(tmp_path):
    import json

    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    db.put(make_claim("CLAIM:drug", "CANDIDATE_THERAPY_FOR", subject_id="CHEBI:1", object_id=A, status="inference", source_type="published"))
    db.put(make_claim("CLAIM:gene", "GENE_ASSOCIATED_WITH_DISEASE", subject_id=G, object_id=A, source_type="published"))
    db.close()
    show, hide = tmp_path / "show.json", tmp_path / "hide.json"
    show.write_text(json.dumps({"hide_drug_claims": False}))
    hide.write_text(json.dumps({"hide_drug_claims": True}))

    def ids(policy):
        c = TestClient(create_app(Settings(real_search=False, store_path=path, policy_path=policy)))
        body = c.get(f"/api/entities/{A}/graph").json()
        return {e["claim_id"] for e in body["edges"]}, c.get("/api/claims/CLAIM:drug").status_code

    assert ids(show) == ({"CLAIM:drug", "CLAIM:gene"}, 200)
    assert ids(hide) == ({"CLAIM:gene"}, 404)
