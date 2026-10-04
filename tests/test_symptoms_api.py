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
