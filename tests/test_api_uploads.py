"""POST /api/uploads: real behaviour (replaces the old canned fixture). Payloads are SYNTHETIC."""

from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.api.settings import Settings

client = TestClient(create_app(Settings(real_search=False)))

OK = {
    "claim_id": "CLAIM:upload-1", "subject_id": "MONDO:0000001", "predicate": "PERTURBS_MECHANISM", "object_id": "HP:0000001",
    "source_url": "https://example.invalid/our-notebook", "source_span": "We saw X in cell line Y.", "lineage_id": "STUDY:our-lab",
    "contributor": "A. Contributor, Example Lab",
}


def post(**kw):
    return client.post("/api/uploads", json={**OK, **kw})


def test_an_upload_is_stored_as_lab_reported_and_unreviewed_and_labelled_a_demo_session():
    r = post(claim_id="CLAIM:upload-ok").json()
    assert r["quarantined"] is False and r["claim"]["source_type"] == "lab_reported" and r["claim"]["review_state"] == "unreviewed"
    assert r["claim"]["status"] == "reported_observation" and "reset" in r["_synthetic"] and "never promoted" in r["_synthetic"]


def test_an_upload_cannot_claim_to_be_reviewed_or_published():
    assert post(review_state="reviewed").status_code == 422  # unknown fields are refused
    assert post(source_type="published").status_code == 422


def test_an_upload_cannot_overwrite_an_existing_claim_id():
    post(claim_id="CLAIM:upload-dup")
    second = post(claim_id="CLAIM:upload-dup", source_span="different text").json()
    assert second["quarantined"] is True and "already exists" in second["error"]


def test_bad_identifiers_unsafe_links_and_private_markers_are_quarantined_with_a_reason():
    assert post(claim_id="CLAIM:u-a", subject_id="HGNC:GBA1").json()["quarantined"] is True  # an ID built from a label
    assert post(claim_id="CLAIM:u-b", source_url="javascript:alert(1)").json()["quarantined"] is True
    leak = post(claim_id="CLAIM:u-c", source_span="notes about CASE\u200b-SYN-0007").json()
    assert leak["quarantined"] is True and "private" in leak["error"]


def test_oversized_and_malformed_uploads_are_refused():
    assert client.post("/api/uploads", content=b"x" * 70_000, headers={"content-type": "application/json"}).status_code in {413, 422}
    assert post(source_span="x" * 5000).status_code == 422
    assert client.post("/api/uploads", json={}).status_code == 422


def test_an_upload_never_appears_in_the_public_claim_endpoints():
    post(claim_id="CLAIM:upload-private-ish")
    assert client.get("/api/claims/CLAIM:upload-private-ish").status_code == 404
