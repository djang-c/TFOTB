"""POST /api/lookup: unknown terms are verified, then added to the shared store only if verified."""

from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.api.settings import Settings
from atlas.terms import Paper, Verdict


def verified(label="Zorn-Quill syndrome"):
    return Verdict(label, "verified", "ok", id="TERM:zorn-quill-syndrome", label=label, kind="condition (found in the literature)",
                   type="disease", method="literature", title_hits=3,
                   papers=[Paper("1", "A paper", "J", "2024", "10.1/x", "https://doi.org/10.1/x")],
                   sources_checked=[{"source": "Europe PMC", "status": "ok", "found": 3}])


def make(tmp_path, verdict=None):
    app = create_app(Settings(real_search=False, store_path=tmp_path / "store" / "atlas.db"))
    calls = []

    def verifier(term):
        calls.append(term)
        return verdict or Verdict(term, "not_verified", "no")

    app.state.term_verifier = verifier
    return TestClient(app), app, calls


def test_a_verified_term_is_added_then_searchable_and_has_an_entity_page(tmp_path):
    c, _, calls = make(tmp_path, verified())
    r = c.post("/api/lookup", json={"query": "Zorn-Quill syndrome"}).json()
    assert r["status"] == "added" and r["stored"] and r["entity_id"] == "TERM:zorn-quill-syndrome" and r["papers"][0]["doi"] == "10.1/x"
    hits = c.get("/api/search", params={"q": "zorn quill"}).json()["results"]
    assert hits[0]["id"] == "TERM:zorn-quill-syndrome" and hits[0]["added_by_lookup"] is True
    page = c.get("/api/entities/TERM:zorn-quill-syndrome").json()
    assert page["claims"] == [] and page["papers"][0]["url"] == "https://doi.org/10.1/x" and page["entity"]["review_state"] == "unreviewed"
    gap = c.get("/api/entities/TERM:zorn-quill-syndrome/gap").json()["gap"]
    assert gap["kind"] == "not_yet_researched" and "Missing is not the same as no connection" in gap["statement"]
    for sub in ("connections", "assets", "actions", "groups", "collaborators", "graph", "related"):
        assert c.get(f"/api/entities/TERM:zorn-quill-syndrome/{sub}").status_code == 200
    again = c.post("/api/lookup", json={"query": "Zorn-Quill syndrome"}).json()
    assert again["status"] == "known" and len(calls) == 1  # the second ask never reaches the public services


def test_an_unverified_term_is_not_stored_and_the_client_is_told_to_keep_it_locally(tmp_path):
    c, app, _ = make(tmp_path)
    r = c.post("/api/lookup", json={"query": "flight of the buffalo"}).json()
    assert r["status"] == "not_verified" and r["stored"] is False
    assert app.state.terms.all() == [] and c.get("/api/terms").json()["total"] == 0


def test_identifying_text_is_refused_and_never_reaches_the_verifier(tmp_path):
    c, _, calls = make(tmp_path)
    r = c.post("/api/lookup", json={"query": "john smith 555-123-4567"}).json()
    assert r["status"] == "rejected" and "personal" in r["reason"] and calls == []


def test_lookups_are_rate_limited_per_client(tmp_path):
    c, app, _ = make(tmp_path)
    app.state.lookup_limiter.per_client = 2
    codes = [c.post("/api/lookup", json={"query": f"thing {chr(97 + i)}x"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_unknown_fields_and_oversize_bodies_are_refused(tmp_path):
    c, _, _ = make(tmp_path)
    assert c.post("/api/lookup", json={"query": "x", "extra": 1}).status_code == 422
    assert c.post("/api/lookup", json={"query": "x" * 301}).status_code == 422


def test_an_unknown_term_id_is_a_404_not_a_crash(tmp_path):
    c, _, _ = make(tmp_path)
    assert c.get("/api/entities/TERM:nope").status_code == 404
    assert c.get("/api/entities/MESH:D000000/graph").status_code == 404


def test_meta_reports_store_counts_including_terms_added(tmp_path):
    c, _, _ = make(tmp_path, verified())
    assert c.get("/api/meta").json()["store"] == {"claims": 0, "papers": 0, "ai_hypotheses": 0, "treatment_ideas": 0, "terms_added": 0}
    c.post("/api/lookup", json={"query": "Zorn-Quill syndrome"})
    assert c.get("/api/meta").json()["store"]["terms_added"] == 1


def test_connection_labels_name_compartments_and_substances_from_the_sidecar():
    from atlas.api.routes import fill_labels

    results = [{"comparisons": [{"context_matches": ["shared GO:0005764[CHEBI:16113]", "directly links: X (CLAIM:a)"]}]}]
    names = {"GO:0005764": "lysosome", "CHEBI:16113": "cholesterol"}
    got = fill_labels({"GO:0005764": "GO:0005764", "HGNC:1": "A"}, results, lambda i: names.get(i, ""))
    assert got == {"GO:0005764": "lysosome", "CHEBI:16113": "cholesterol", "HGNC:1": "A"}  # an existing real label is kept
    assert fill_labels({}, results, lambda i: "") == {}  # nothing names it: no entry, the ID is shown
