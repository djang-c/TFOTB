"""Real-mode Q3 cards. The mini ontology and the ClinicalTrials.gov response are SYNTHETIC."""

from atlas.resolver import DISEASE, GENE, TIER_EXACT, Resolver
from atlas.search import SearchIndex
from atlas.trials import TrialsSource


def index(response):
    r = Resolver()
    r.add(DISEASE, "MONDO:9000001", "Example disease", [("Example syndrome", TIER_EXACT)], ["OMIM:900001"])
    r.add(GENE, "HGNC:900001", "EXG1", [])
    ix = SearchIndex(r, None, [{"gene_symbol": "EXG1", "association_type": "MENDELIAN", "disease_id": "OMIM:900001"}], {})
    ix.trials = TrialsSource(fetch=lambda url: response)
    return ix


def study(nct, status):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": f"Study {nct}"},
        "statusModule": {"overallStatus": status, "lastUpdatePostDateStruct": {"date": "2026-01-01"}},
        "conditionsModule": {"conditions": ["Example disease"]},
        "designModule": {"studyType": "OBSERVATIONAL"},
    }}


def test_brief_plus_reuse_cards_for_open_studies_only_and_no_outreach():
    ix = index({"totalCount": 2, "studies": [study("NCT90000001", "RECRUITING"), study("NCT90000002", "COMPLETED")]})
    kinds = [c["kind"] for c in ix.actions("MONDO:9000001")]
    assert kinds == ["evidence_brief", "asset_reuse"]  # completed study gets no card; registry pages are not contacts


def test_unknown_entry_gets_no_cards():
    assert index({"studies": []}).actions("MONDO:9999999") == []


def test_graph_marks_computed_links_as_unsourced_and_gene_links_as_claims():
    ix = index({"studies": []})
    g = ix.graph("HGNC:900001")
    assert {n["id"] for n in g["nodes"]} == {"HGNC:900001", "MONDO:9000001"}
    (edge,) = g["edges"]
    assert edge["claim_id"] in ix.store.claims and edge["predicate"] == "GENE_ASSOCIATED_WITH_DISEASE"
    for e in ix.graph("MONDO:9000001")["edges"]:
        if e["predicate"] == "SIMILAR_SYMPTOMS":
            assert e["claim_id"] is None and e["status"] == "computational_prediction"


def test_summary_points_to_genes_on_subtypes_instead_of_saying_none():
    r = Resolver()
    r.add(DISEASE, "MONDO:9000010", "Parent disease", [])
    r.add(DISEASE, "MONDO:9000011", "Parent disease, type 1", [], ["OMIM:900011"])
    r.add(GENE, "HGNC:900011", "PDG1", [])
    rows = [{"gene_symbol": "PDG1", "association_type": "MENDELIAN", "disease_id": "OMIM:900011"}]
    ix = SearchIndex(r, None, rows, {"MONDO:9000011": {"MONDO:9000010"}})
    ix.trials = TrialsSource(fetch=lambda url: {"studies": []})
    text = " ".join(x["text"] for x in ix.summary("MONDO:9000010"))
    assert "No gene is linked to it" not in text
    assert "PDG1 (Parent disease, type 1)" in text and "1 more specific form of it" in text
    assert ix.hierarchy_note("MONDO:9000010", "MONDO:9000011") == "a more specific form of this disease"
    assert ix.hierarchy_note("MONDO:9000011", "MONDO:9000010") == "a broader group that includes this disease"


def test_symptom_text_is_split_into_hpo_terms_and_unresolved_phrases_are_reported_not_guessed():
    from atlas.resolver import PHENOTYPE

    r = Resolver()
    r.add(DISEASE, "MONDO:9000001", "Example disease", [])
    r.add(PHENOTYPE, "HP:0000001", "Seizure", [("seizures", TIER_EXACT)])
    r.add(PHENOTYPE, "HP:0000002", "Ataxia", [])
    r.add(PHENOTYPE, "HP:0000003", "Visual loss", [("vision loss", TIER_EXACT)])
    ix = SearchIndex(r, None, [], {})
    got = ix.symptom_terms("seizures, vision loss and nonsense words")
    assert [(t["text"], t["status"]) for t in got] == [("seizures", "resolved"), ("vision loss", "resolved"), ("nonsense words", "unresolved")]
    sentence = ix.symptom_terms("seizures vision loss ataxia")  # no separators: longest exact names, left to right
    assert [t["id"] for t in sentence] == ["HP:0000001", "HP:0000003", "HP:0000002"]
    typed = ix.symptom_terms("HP:0000002, HP:9999999")
    assert [(t["id"], t["status"]) for t in typed] == [("HP:0000002", "resolved"), (None, "unresolved")]
    dup = ix.symptom_terms("seizures, Seizure")
    assert [t["id"] for t in dup] == ["HP:0000001"]  # the same term twice counts once
    out = ix.symptom_search("seizures")
    assert out["candidates"] == [] and "not diagnoses" in out["note"]  # no phenotype channel: nothing is invented
