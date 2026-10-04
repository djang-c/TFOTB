"""GARD patient groups, offline. The records below are SYNTHETIC (format-valid IDs, made-up groups)."""

from atlas.gard import ACCOUNTS, GardSource

RECORD = {"MONDO_ID__c": "MONDO:9000001", "Name": "Example disease", "encodedName": "example-disease",
          "Organization_Supported_Diseases__c": [
              {"Account_Name__c": "Example Families Network", "Website__c": "https://example.invalid/"},
              {"Account_Name__c": "No Site Group", "Website__c": "not a url"}]}
ACCTS = [{"acct": {"Name": "Example Families Network", "Website": "https://www.example.invalid",
                   "Country__c": "Canada", "Patient_Registry_URL__c": "https://example.invalid/registry",
                   "RecordType": {"Name": "Patient Advocacy Group"}}}]


def source(record=RECORD):
    return GardSource(fetch=lambda url: ACCTS if url == ACCOUNTS else record)


def test_groups_are_shown_as_listed_with_registry_and_note():
    out = source().for_disease("MONDO:9000001", ["GARD:0000001"])
    assert out["status"] == "ok" and [g["name"] for g in out["groups"]] == ["Example Families Network", "No Site Group"]
    first = out["groups"][0]
    assert first["country"] == "Canada" and first["registry_url"] == "https://example.invalid/registry"
    assert out["groups"][1]["website"] is None  # not a URL: no link is made up
    assert "not an endorsement" in out["note"] and out["pages"][0]["url"].endswith("/1/example-disease")


def test_record_for_another_disease_is_rejected_not_used():
    out = source({**RECORD, "MONDO_ID__c": "MONDO:9000099"}).for_disease("MONDO:9000001", ["GARD:0000001"])
    assert out["groups"] == [] and out["rejected"] == 1


def test_no_cross_reference_and_failure_are_reported_honestly():
    assert source().for_disease("MONDO:9000001", [])["status"] == "no_xref"
    def boom(url):
        raise OSError("down")
    assert GardSource(fetch=boom).for_disease("MONDO:9000001", ["GARD:0000001"])["status"] == "failed"
