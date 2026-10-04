"""Related-disease tests. Entities and claims are SYNTHETIC (software behaviour only)."""

from types import SimpleNamespace

from tests.conftest import make_claim

from atlas.related import NONE_NOTE, from_reference, from_store, related_diseases

A, B, C, D, P = (f"MONDO:900000{i}" for i in (1, 2, 3, 4, 9))
G = "HGNC:1"


class FakePh:
    def __init__(self, scores):
        self.scores = scores

    def retrieve_candidates(self, q, ctx):
        return list(self.scores)

    def compare(self, q, cand, ctx):
        return SimpleNamespace(availability="available", score=self.scores[cand], context_matches=["HP:1 Seizure"])


def fake_ix(**kw):
    base = dict(excluded=set(), genes_of={}, diseases_of={}, parents={}, children={}, ph=None,
                subtype_genes=lambda _i: [], r=SimpleNamespace(label_of=lambda i: f"name {i}"))
    base.update(kw)
    return SimpleNamespace(**base)


def test_shared_gene_lists_every_other_disease_with_both_claims():
    ix = fake_ix(genes_of={A: [{"id": G, "claim_id": "CLAIM:ga"}]},
                 diseases_of={G: [{"id": A, "claim_id": "CLAIM:ga"}, {"id": B, "claim_id": "CLAIM:gb"}]})
    out = from_reference(ix, A)
    assert list(out) == [B]
    r = out[B][0]
    assert r["kind"] == "gene" and r["claim_ids"] == ["CLAIM:ga", "CLAIM:gb"] and r["evidence"] == "reference"


def test_siblings_under_a_specific_parent_are_family_but_a_broad_parent_is_skipped():
    ix = fake_ix(parents={A: {P}}, children={P: {A, B, C}})
    assert set(from_reference(ix, A)) == {B, C}
    broad = fake_ix(parents={A: {P}}, children={P: {A, *(f"MONDO:x{i}" for i in range(50))}})
    assert from_reference(broad, A) == {}


def test_symptom_similarity_keeps_only_scores_at_or_above_the_threshold_best_first():
    ix = fake_ix(ph=FakePh({B: 0.39, C: 0.8, D: 0.5}))
    out = from_reference(ix, A)
    assert set(out) == {C, D} and out[C][0]["score"] == 0.8 and out[C][0]["shared"] == ["Seizure"]


def test_ai_hypothesis_and_paper_links_are_labelled_by_origin():
    ai = make_claim("CLAIM:HYP-1", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=B, source_type="ai_generated",
                    status="inference", source_span="AI hypothesis: both store cholesterol", derived_from=("CLAIM:x", "CLAIM:y"))
    paper = make_claim("CLAIM:p", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=C, object_id=A, source_type="published",
                       status="inference")
    upload = make_claim("CLAIM:u", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=D, source_type="lab_reported",
                         status="inference")
    out = from_store(A, {c.claim_id: c for c in (ai, paper, upload)})
    assert out[B][0]["kind"] == "ai_hypothesis" and out[B][0]["detail"] == "both store cholesterol"
    assert out[B][0]["derived_from"] == ["CLAIM:x", "CLAIM:y"]
    assert out[C][0]["kind"] == "paper_link" and out[C][0]["evidence"] == "paper_hypothesis"
    assert D not in out  # an unreviewed upload never links diseases here


def test_one_row_per_disease_with_all_reasons_more_reasons_first():
    ref = {B: [{"kind": "symptoms", "key": "phenotype", "score": 0.9, "claim_ids": []}],
           C: [{"kind": "gene", "key": G, "claim_ids": []}, {"kind": "symptoms", "key": "phenotype", "score": 0.5, "claim_ids": []}]}
    out = related_diseases(A, ref, {C: [{"kind": "gene", "key": G, "claim_ids": []}]})
    assert [d["id"] for d in out["diseases"]] == [C, B]
    assert out["diseases"][0]["kinds"] == ["gene", "symptoms"] and len(out["diseases"][0]["reasons"]) == 2
    assert out["counts"]["gene"] == 1 and out["none"] is False


def test_no_reason_says_no_similarities_plainly():
    out = related_diseases(A, {}, {})
    assert out["none"] is True and out["diseases"] == [] and out["note"] == NONE_NOTE
    assert out["note"].startswith("No similarities found")
    assert "not been generated" in out["ai"]["note"] or "generated yet" in out["ai"]["note"]


def test_api_lists_related_diseases_from_stored_claims_and_says_none_otherwise(tmp_path):
    from fastapi.testclient import TestClient

    from atlas.api import create_app
    from atlas.api.settings import Settings
    from atlas.db import AtlasDB

    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    db.put(make_claim("CLAIM:p", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id="SYN:disease-a", object_id=B,
                      source_type="published", status="inference"))
    db.close()
    client = TestClient(create_app(Settings(real_search=False, store_path=path)))
    r = client.get("/api/entities/SYN:disease-a/related-diseases").json()
    assert r["applies"] is True and [d["id"] for d in r["diseases"]] == [B] and r["diseases"][0]["kinds"] == ["paper_link"]
    lone = client.get("/api/entities/SYN:disease-e/related-diseases").json()
    assert lone["none"] is True and lone["note"].startswith("No similarities found")
    assert client.get("/api/entities/SYN:gene-1/related-diseases").json()["applies"] is False
