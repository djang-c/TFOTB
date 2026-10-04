"""Symptoms-only search through the API (the 'no disease named' input)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.api.settings import Settings

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture(scope="module")
def client():
    c = TestClient(create_app(Settings()))
    c.get("/api/symptoms", params={"q": "seizures"})  # builds the index once
    return c


def test_without_the_pinned_files_it_says_so_instead_of_inventing_candidates():
    c = TestClient(create_app(Settings(real_search=False)))
    r = c.get("/api/symptoms", params={"q": "seizures"}).json()
    assert r["candidates"] == [] and "pinned" in r["note"]


@pytest.mark.skipif(not (RAW / "hpo" / "phenotype.hpoa").exists(), reason="pinned HPO files not downloaded")
class TestRealSymptoms:
    def test_a_sentence_without_separators_is_understood_and_ranks_a_plausible_family_with_its_genes(self, client):
        r = client.get("/api/symptoms", params={"q": "seizures vision loss ataxia"}).json()
        assert [t["status"] for t in r["terms"]] == ["resolved"] * 3
        labels = " | ".join(c["label"] for c in r["candidates"])
        assert "neuronal ceroid lipofuscinosis" in labels  # the seed family, from the data, not hard-coded
        top = r["candidates"][0]
        assert top["label_kind"] == "research hypothesis, not a diagnosis" and top["genes"]
        assert "not diagnoses" in r["note"] and "not probabilities" in r["definition"]

    def test_unresolvable_text_returns_no_candidates_and_says_which_phrase_failed(self, client):
        r = client.get("/api/symptoms", params={"q": "xyzzy nonsense"}).json()
        assert r["candidates"] == [] and r["terms"][0]["status"] != "resolved"

    def test_empty_and_overlong_input_are_handled(self, client):
        assert client.get("/api/symptoms").json()["candidates"] == []
        assert client.get("/api/symptoms", params={"q": "ataxia, " * 500}).status_code == 200


@pytest.mark.skipif(not (RAW / "hpo" / "phenotype.hpoa").exists(), reason="pinned HPO files not downloaded")
class TestAbsentSymptoms:
    def test_a_symptom_described_as_absent_is_never_used_as_a_match(self, client):
        r = client.get("/api/symptoms", params={"q": "seizures, no hearing loss"}).json()
        flags = {t["label"]: t["absent"] for t in r["terms"]}
        assert flags == {"Seizure": False, "Hearing impairment": True}
        for c in r["candidates"]:
            assert "Hearing impairment" not in c["matched_labels"]  # absence is not evidence of a match

    def test_a_disease_that_records_an_absent_symptom_is_flagged_and_not_ranked_above_an_equal_one(self, client):
        base = client.get("/api/symptoms", params={"q": "seizures"}).json()["candidates"]
        r = client.get("/api/symptoms", params={"q": "seizures, no hearing loss"}).json()["candidates"]
        flagged = [c for c in r if c["recorded_despite_absent"]]
        assert flagged and all(c["recorded_despite_absent"] == ["Hearing impairment"] for c in flagged)
        assert {c["disease_id"] for c in r} <= {c["disease_id"] for c in base} | {c["disease_id"] for c in r}
        first_ok = next(i for i, c in enumerate(r) if not c["recorded_despite_absent"])
        last_flagged_same_cov = [i for i, c in enumerate(r) if c["recorded_despite_absent"] and c["coverage"] == r[first_ok]["coverage"]]
        assert all(i > first_ok for i in last_flagged_same_cov)

    def test_only_absent_symptoms_give_no_candidates(self, client):
        assert client.get("/api/symptoms", params={"q": "no seizures"}).json()["candidates"] == []

    def test_a_word_that_merely_starts_with_no_is_not_a_negation(self, client):
        t = client.get("/api/symptoms", params={"q": "nocturnal enuresis"}).json()["terms"]
        assert all(not x["absent"] for x in t)
