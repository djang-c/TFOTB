"""ClinicalTrials.gov assets, offline. The API responses below are SYNTHETIC (format-valid NCT IDs)."""

from atlas.trials import TrialsSource


def study(nct, title, status, conditions, updated="2026-01-01"):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": title},
        "statusModule": {"overallStatus": status, "lastUpdatePostDateStruct": {"date": updated}},
        "conditionsModule": {"conditions": conditions},
        "designModule": {"studyType": "OBSERVATIONAL"},
    }}


RESPONSE = {"totalCount": 3, "studies": [
    study("NCT90000001", "Closed study", "COMPLETED", ["Example Disease Type C"], "2025-01-01"),
    study("NCT90000002", "Broader study", "RECRUITING", ["Some related disorder"]),
    study("NCT90000003", "Open study", "RECRUITING", ["example disease, type C", "Other"], "2024-01-01"),
]}


def source(response=RESPONSE):
    return TrialsSource(fetch=lambda url: response)


def test_only_studies_listing_the_disease_by_name_are_kept_and_counted():
    out = source().for_disease("MONDO:9000001", "Example disease type C", set())
    assert [a["asset_id"] for a in out["assets"]] == ["ASSET:ctgov-NCT90000003", "ASSET:ctgov-NCT90000001"]  # open first
    assert out["coverage"]["fetched"] == 3 and out["coverage"]["screened"] == 2


def test_each_asset_has_a_claim_quoting_the_matched_condition():
    out = source().for_disease("MONDO:9000001", "Example disease type C", set())
    claim = out["claims"][out["assets"][0]["relevance_claim_ids"][0]]
    assert claim["source_span"] == "example disease, type C"
    assert (claim["subject_id"], claim["predicate"]) == ("NCT:90000003", "ASSET_RELEVANT_TO")


def test_terms_obligations_are_carried_with_the_data():
    out = source().for_disease("MONDO:9000001", "Example disease type C", set())
    assert "ClinicalTrials.gov" in out["attribution"] and out["modifications"]
    assert any("last updated on ClinicalTrials.gov" in r for r in out["assets"][0]["ranking_reasons"])


def test_network_failure_is_reported_not_zero():
    def boom(url):
        raise OSError("timed out")
    out = TrialsSource(fetch=boom).for_disease("MONDO:9000001", "Example disease type C", set())
    assert out["assets"] == [] and out["coverage"]["status"] == "failed"
