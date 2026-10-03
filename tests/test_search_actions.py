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
