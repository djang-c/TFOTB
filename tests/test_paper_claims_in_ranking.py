"""Audit A/D/E (High): claims read from papers must take part in the ranking, not only in the graph.
Ontology, genes and claims here are SYNTHETIC (software behaviour only)."""

from pathlib import Path

import pytest
from tests.conftest import make_claim

from atlas.resolver import DISEASE, GENE, Resolver
from atlas.schemas import EvidenceCategory, SourceCoverage, SourceStatus
from atlas.search import SearchIndex

A, B = "MONDO:9000001", "MONDO:9000002"


def index():
    r = Resolver()
    r.add(DISEASE, A, "Disease alpha", [], ["OMIM:900001"])
    r.add(DISEASE, B, "Disease beta", [], ["OMIM:900002"])
    r.add(GENE, "HGNC:900001", "EXG1", [])
    return SearchIndex(r, None, [{"gene_symbol": "EXG1", "association_type": "MENDELIAN", "disease_id": "OMIM:900001"}], {})


def paper_claims():
    out = {}
    for cid, d in (("CLAIM:PMID-1-a", A), ("CLAIM:PMID-2-b", B)):
        out[cid] = make_claim(
            cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id="GO:0005764", source_type="published",
            lineage=f"STUDY:{cid}", context={"substance": "CHEBI:16113", "scope": "new_finding"},
            source_url="https://doi.org/10.1000/x", extraction_method="llm:m@extract-v5",
        )
    return out


def test_without_paper_claims_two_diseases_with_no_shared_symptoms_are_not_connected():
    assert index().connections(A)["results"] == []


def test_paper_claims_make_a_literature_supported_lead_and_the_brief_cites_them():
    ix = index()
    cov = SourceCoverage(source="Paper claims", status=SourceStatus.ok, fetched=4, screened=2, error="2 papers read")
    ix.set_paper_claims(paper_claims(), version=1, coverage=cov)
    res = ix.connections(A)
    (row,) = res["results"]
    assert row["candidate_id"] == B and row["category"] == EvidenceCategory.literature_supported_lead.value
    assert any(s["source"] == "Paper claims" for s in res["coverage"]["per_source"])
    body = ix.actions(A)[0]["body_markdown"]
    assert "found by AI in https://doi.org/10.1000/x" in body and "[^c:CLAIM:PMID-1-a]" in body


def test_changing_the_store_version_drops_cached_results_and_the_same_version_keeps_them():
    ix = index()
    ix.set_paper_claims(paper_claims(), version=1)
    first = ix.connections(A)
    assert ix.connections(A)["results"] == first["results"] and ix._outcomes  # cached
    ix.set_paper_claims({}, version=2)  # the store was rebuilt without the claims
    assert not ix._outcomes and ix.connections(A)["results"] == []  # never served stale


def test_an_ai_hypothesis_in_the_store_does_not_create_a_lead():
    ix = index()
    hyp = make_claim(
        "CLAIM:HYP-1", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=B, status="inference",
        source_type="ai_generated", source_url="atlas:ai-hypothesis",
    )
    ix.set_paper_claims({"CLAIM:HYP-1": hyp}, version=1)
    cats = {r["category"] for r in ix.connections(A)["results"]}
    assert EvidenceCategory.literature_supported_lead.value not in cats
    assert EvidenceCategory.reviewed_mechanistic_lead.value not in cats


RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.mark.skipif(not (RAW / "mondo" / "mondo.json").exists(), reason="pinned ontology files not downloaded")
def test_real_seed_pair_is_listed_both_ways_when_the_seed_paper_is_stored(tmp_path):
    """The journey the demo is built on, on the real ontologies with the real seed-paper claims."""
    from fastapi.testclient import TestClient

    from atlas.api import create_app
    from atlas.api.settings import Settings
    from atlas.db import AtlasDB

    (tmp_path / "store").mkdir()
    db = AtlasDB(tmp_path / "store" / "atlas.db")
    for cid, d in (("CLAIM:PMID-37245481-a", "MONDO:0008767"), ("CLAIM:PMID-37245481-b", "MONDO:0018982")):
        db.put(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id="GO:0005764", source_type="published",
                          lineage=f"STUDY:{cid}", context={"substance": "CHEBI:16113", "scope": "background"},
                          source_url="https://doi.org/10.1016/j.ebiom.2023.104628", extraction_method="llm:m@extract-v5"))
    db.close()
    c = TestClient(create_app(Settings(store_path=tmp_path / "store" / "atlas.db")))
    for q, other in (("MONDO:0008767", "MONDO:0018982"), ("MONDO:0018982", "MONDO:0008767")):
        rows = {r["candidate_id"]: r for r in c.get(f"/api/entities/{q}/connections").json()["results"]}
        assert other in rows and rows[other]["category"] == "literature-supported lead"

    # the entry page's data lists the paper claims that name it, so the page can show its sources
    page = c.get("/api/entities/MONDO:0008767").json()
    assert [x["claim_id"] for x in page["claims"]] == ["CLAIM:PMID-37245481-a"]
    assert page["claim_counts_by_predicate"] == {"ACCUMULATES_IN_COMPARTMENT": 1}
