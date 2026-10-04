"""Collaborator view tests. Papers, authors and claims are SYNTHETIC (software behaviour only)."""

import json

from fastapi.testclient import TestClient
from tests.conftest import make_claim

from atlas.api import create_app
from atlas.api.settings import Settings
from atlas.collaborators import NOTE, collaborators_for, load_papers
from atlas.sources import authors_of

A, B, C = "MONDO:9000001", "MONDO:9000002", "MONDO:9000003"


def claim(src, disease, n=1):
    return make_claim(
        f"CLAIM:PMID-{src}-{n}", "ACCUMULATES_IN_COMPARTMENT", subject_id=disease, object_id="GO:0005764",
        source_type="published", lineage=f"STUDY:PMID-{src}",
    )


def paper(src, *authors):
    return {"source_id": f"PMID:{src}", "title": f"Paper {src}", "journal": "J", "year": "2026", "citation": f"https://doi.org/10.1/{src}",
            "authors": [{"name": n, "orcid": o, "affiliation": None} for n, o in authors]}


PAPERS = {
    "PMID:1": paper(1, ("Rivera A", "0000-0001-0000-0001"), ("Shared P", None)),
    "PMID:2": paper(2, ("Rivera A", "0000-0001-0000-0001"), ("Other Q", None)),
    "PMID:3": paper(3, ("Shared P", None), ("Third T", None)),
}
CLAIMS = {c.claim_id: c for c in (claim(1, A), claim(2, B), claim(3, C))}


def test_a_person_on_papers_about_two_diseases_is_a_bridge_and_both_sides_cite_claims():
    out = collaborators_for(A, CLAIMS, PAPERS)
    rivera = next(i for i in out["items"] if i["name"] == "Rivera A")
    assert rivera["match"] == "ORCID" and rivera["other_papers"] == 1
    assert [a["entity_id"] for a in rivera["also_studies"]] == [B]
    assert rivera["papers"][0]["claim_ids"] == ["CLAIM:PMID-1-1"] and rivera["also_studies"][0]["claim_ids"] == ["CLAIM:PMID-2-1"]


def test_a_name_only_match_is_labelled_unverified_and_orcid_matches_are_not():
    out = collaborators_for(A, CLAIMS, PAPERS)
    shared = next(i for i in out["items"] if i["name"] == "Shared P")
    assert shared["match"] == "name only (unverified)" and [a["entity_id"] for a in shared["also_studies"]] == [C]
    assert "name alone" in out["note"] and out["note"] == NOTE


def test_people_with_no_paper_about_the_entity_are_not_listed_and_ordering_puts_bridges_first():
    out = collaborators_for(A, CLAIMS, PAPERS)
    names = [i["name"] for i in out["items"]]
    assert "Other Q" not in names and "Third T" not in names  # they never appear on a paper about A
    assert names[0] == "Rivera A" and out["bridges"] == 2


def test_papers_without_metadata_or_a_pmid_lineage_are_ignored_not_guessed():
    orphan = make_claim("CLAIM:x", "ACCUMULATES_IN_COMPARTMENT", subject_id=A, object_id="GO:0005764", lineage="STUDY:s1")
    out = collaborators_for(A, {"CLAIM:x": orphan, **CLAIMS}, {})
    assert out["items"] == [] and out["papers_considered"] == 0


def test_authors_are_taken_exactly_from_the_record_with_orcid_only_when_typed_orcid():
    rec = {"authorList": {"author": [
        {"fullName": "Doe J", "authorId": {"type": "ORCID", "value": "0000-0002-1825-0097"},
         "authorAffiliationDetailsList": {"authorAffiliation": [{"affiliation": "Some University"}]}},
        {"fullName": "Roe R", "authorId": {"type": "SCOPUS", "value": "123"}},
        {"fullName": ""},
    ]}}
    got = authors_of(rec)
    assert got[0] == {"name": "Doe J", "orcid": "0000-0002-1825-0097", "affiliation": "Some University"}
    assert got[1]["orcid"] is None and len(got) == 2


def test_the_endpoint_serves_the_view_and_an_empty_store_gives_an_empty_labelled_list(tmp_path):
    from atlas.db import AtlasDB

    store = tmp_path / "store"
    store.mkdir()
    db = AtlasDB(store / "atlas.db")
    for c in CLAIMS.values():
        db.put(c)
    db.close()
    (store / "papers.jsonl").write_text("\n".join(json.dumps(p) for p in PAPERS.values()) + "\n")
    c = TestClient(create_app(Settings(real_search=False, store_path=store / "atlas.db")))
    # the synthetic entity route needs an indexed id; use a SYN entity for the 404 check and call the function path directly
    assert load_papers(store).keys() == PAPERS.keys()
    r = c.get("/api/entities/SYN:disease-a/collaborators").json()
    assert r["items"] == [] and "note" in r and "name alone" in r["note"]
