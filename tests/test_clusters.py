"""Mechanism cluster tests. Claims are SYNTHETIC (software behaviour only)."""

from tests.conftest import make_claim

from atlas.clusters import LIMITATION, RULE, mechanism_clusters

A, B, C, D, E = (f"MONDO:900000{i}" for i in range(1, 6))
GO = "GO:0005764"


def acc(cid, disease, substance="CHEBI:16113", obj=GO, **kw):
    kw.setdefault("source_type", "published")
    kw.setdefault("lineage", f"STUDY:{cid}")
    return make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=disease, object_id=obj, context={"substance": substance}, **kw)


def build(*cs):
    return {c.claim_id: c for c in cs}


def test_diseases_sharing_a_compartment_and_substance_form_one_cluster_with_their_claims():
    out = mechanism_clusters(build(acc("CLAIM:a", A), acc("CLAIM:b", B), acc("CLAIM:c", C, substance="CHEBI:99999")))
    assert len(out) == 1 and [d["id"] for d in out[0]["diseases"]] == [A, B]  # C stores a different substance
    feat = out[0]["shared_features"][0]
    assert feat["feature"] == f"{GO}[CHEBI:16113]" and feat["claim_ids"] == ["CLAIM:a", "CLAIM:b"] and feat["studies"] == 2


def test_clusters_are_connected_groups_not_just_pairs():
    cs = build(acc("CLAIM:a", A), acc("CLAIM:b", B), acc("CLAIM:b2", B, obj="GO:0005770"), acc("CLAIM:c", C, obj="GO:0005770"),
               acc("CLAIM:lone", E, obj="GO:0000001"))
    out = mechanism_clusters(cs)
    assert len(out) == 1 and {d["id"] for d in out[0]["diseases"]} == {A, B, C}  # A-B via lysosome, B-C via late endosome


def test_hypotheses_predictions_uploads_and_non_credible_claims_never_create_a_link():
    for kw in ({"source_type": "ai_generated"}, {"source_type": "lab_reported"}, {"source_type": "synthetic_fixture"},
               {"status": "computational_prediction"}):
        assert mechanism_clusters(build(acc("CLAIM:a", A), acc("CLAIM:b", B, **kw))) == [], kw


def test_a_feature_shared_by_too_many_diseases_is_skipped_as_too_generic():
    many = build(*(acc(f"CLAIM:{i}", f"MONDO:{9100000 + i}") for i in range(6)))
    assert mechanism_clusters(many, max_feature_degree=5) == [] and len(mechanism_clusters(many, max_feature_degree=6)) == 1


def test_every_cluster_states_its_rule_and_that_it_is_not_a_shared_treatment_claim():
    (cluster,) = mechanism_clusters(build(acc("CLAIM:a", A), acc("CLAIM:b", B)))
    assert cluster["rule"] == RULE and cluster["limitation"] == LIMITATION and "treatment" in LIMITATION


def test_labels_are_used_when_given_and_output_is_deterministic():
    cs = build(acc("CLAIM:b", B), acc("CLAIM:a", A))
    lab = {GO: "lysosome", "CHEBI:16113": "cholesterol", A: "Disease A"}.get
    one = mechanism_clusters(cs, label_of=lambda i: lab(i, ""))
    assert one == mechanism_clusters(dict(reversed(list(cs.items()))), label_of=lambda i: lab(i, ""))
    assert one[0]["shared_features"][0]["label"] == "lysosome (cholesterol)" and one[0]["diseases"][0]["label"] == "Disease A"


def test_the_endpoint_serves_clusters_from_the_store(tmp_path):
    from fastapi.testclient import TestClient

    from atlas.api import create_app
    from atlas.api.settings import Settings
    from atlas.db import AtlasDB

    path = tmp_path / "atlas.db"
    db = AtlasDB(path)
    for c in (acc("CLAIM:a", A), acc("CLAIM:b", B)):
        db.put(c)
    db.close()
    r = TestClient(create_app(Settings(real_search=False, store_path=path))).get("/api/clusters").json()
    assert r["total"] == 1 and "not a statement" in r["note"]


def _cmp(channel, matches=(), score=None, refs=(), availability="available"):
    return {"channel_id": channel, "availability": availability, "score": score, "context_matches": list(matches),
            "supporting_claim_ids": list(refs), "contradicting_claim_ids": []}


def test_groups_around_one_entry_name_the_shared_feature_and_keep_the_evidence():
    from atlas.clusters import groups_for

    names = {"GO:0005764": "lysosome", "CHEBI:16113": "cholesterol", "HGNC:2074": "CLN3", "MONDO:2": "B", "MONDO:3": "C"}
    results = [
        {"candidate_id": "MONDO:2", "category": "literature-supported lead", "comparisons": [
            _cmp("molecular_mechanisms", ["shared GO:0005764[CHEBI:16113]", "directly links the two diseases: SHARES_PATHOGENIC_PATHWAY_WITH (CLAIM:x)"], refs=["CLAIM:a"]),
            _cmp("phenotype", ["HP:0000709 Psychosis"], score=0.41),
        ]},
        {"candidate_id": "MONDO:3", "category": "symptom-level lead", "comparisons": [
            {**_cmp("dna_variants", ["shared HGNC:2074"]), "limitations": ["same HGNC:2074 reported on both sides, not variant-level evidence: CLAIM:g1, CLAIM:g2"]},
            _cmp("phenotype", score=0.2),  # below the similarity floor: not a symptom-group member
            _cmp("molecular_mechanisms", ["shared GO:0005764[CHEBI:16113]"], availability="missing"),  # missing never counts
        ]},
    ]
    g = groups_for("MONDO:1", results, label_of=lambda i: names.get(i, ""))
    assert [(x["kind"], x["label"]) for x in g] == [
        ("mechanism", "lysosome (cholesterol)"), ("gene", "CLN3"), ("direct", "SHARES_PATHOGENIC_PATHWAY_WITH"),
        ("symptoms", "similar recorded symptoms")]
    assert g[0]["members"] == [{"id": "MONDO:2", "label": "B", "category": "literature-supported lead", "claim_ids": ["CLAIM:a"]}]
    assert g[1]["members"][0]["claim_ids"] == ["CLAIM:g1", "CLAIM:g2"]  # gene membership cites the claims on both sides
    assert g[2]["members"][0]["claim_ids"] == ["CLAIM:x"]  # a direct link cites the claim that states it, nothing else
    own = groups_for("MONDO:1", results, label_of=lambda i: names.get(i, ""), feature_claims={"GO:0005764[CHEBI:16113]": ["CLAIM:obs"]})
    assert own[0]["members"][0]["claim_ids"] == ["CLAIM:obs"]  # a mechanism group cites only that feature's observed claims
    assert [m["id"] for m in g[3]["members"]] == ["MONDO:2"] and g[3]["members"][0]["shared"] == ["Psychosis"]


def test_no_connections_means_no_groups():
    from atlas.clusters import groups_for

    assert groups_for("MONDO:1", []) == []
