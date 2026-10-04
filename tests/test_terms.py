"""Lookup of terms the catalogue has never seen: verification rules and the term store (no network)."""

import json
import urllib.parse

import pytest

from atlas.terms import TermRejected, TermStore, clean_term, verify_term


def fake_fetch(mesh=None, hits=0, fail=None):
    """A stand-in for the two public services. `mesh` is the esummary record (None = not in MeSH)."""
    calls = []

    def fetch(url):
        calls.append(url)
        if fail and fail in url:
            raise OSError("down")
        if "esearch.fcgi" in url:
            return json.dumps({"esearchresult": {"idlist": ["1"] if mesh else []}}).encode()
        if "esummary.fcgi" in url:
            return json.dumps({"result": {"1": mesh}}).encode()
        if "europepmc" in url:
            q = urllib.parse.unquote(url)
            papers = [{"pmid": str(i), "title": f"Paper {i}.", "journalTitle": "J", "pubYear": "2024", "doi": f"10.1/x{i}"}
                      for i in range(min(hits, 5))]
            assert "PUB_TYPE:\"Journal Article\"" in q and "NOT PUB_TYPE:\"Retracted Publication\"" in q
            return json.dumps({"hitCount": hits, "resultList": {"result": papers}}).encode()
        raise AssertionError(url)

    fetch.calls = calls
    return fetch


SEIZURES = {"ds_meshui": "D012640", "ds_meshterms": ["Seizures", "Seizure", "Fits"], "ds_scopenote": "Disturbances.",
            "ds_idxlinks": [{"treenum": "C10.597.742"}, {"treenum": "C23.888.592.742"}]}
ML = {"ds_meshui": "D000069550", "ds_meshterms": ["Machine Learning"],
      "ds_idxlinks": [{"treenum": "G17.035.250.500"}, {"treenum": "L01.224.050.375.530"}]}
GEOGRAPHY = {"ds_meshui": "D005060", "ds_meshterms": ["Europe"], "ds_idxlinks": [{"treenum": "Z01.542"}]}


@pytest.mark.parametrize("text", ["jane@x.org", "see https://x.org", "patient 5551234567", "born 12/03/1980", "MRN 12", "CASE-SYN-4",
                                  "a" * 81, "one two three four five six seven eight nine", "12", ""])
def test_identifier_like_or_malformed_text_is_refused_before_anything_is_sent(text):
    with pytest.raises(TermRejected):
        clean_term(text)


def test_a_normal_term_is_tidied_not_refused():
    assert clean_term("  Niemann-Pick \u200bdisease\ttype C ") == "Niemann-Pick disease type C"
    assert clean_term("CLN3") == "CLN3"


def test_a_mesh_symptom_is_verified_with_its_kind_and_papers():
    v = verify_term("seizures", fetch=fake_fetch(SEIZURES, hits=40), wait_s=0)
    assert v.status == "verified" and v.id == "MESH:D012640" and v.kind == "symptom" and v.type == "phenotype"
    assert v.method == "MeSH" and v.synonyms == ["Seizure", "Fits"] and len(v.papers) == 5 and v.title_hits == 40
    assert v.papers[0].url == "https://doi.org/10.1/x0"  # taken from the paper's own record


def test_a_mesh_heading_in_a_non_medical_branch_is_not_a_medical_term():
    for rec in (ML, GEOGRAPHY):  # ML is filed under G17 (mathematical concepts) and L01 (information science)
        v = verify_term("x", fetch=fake_fetch(rec), wait_s=0)
        assert v.status == "not_medical" and v.id is None


def test_a_condition_name_missing_from_mesh_needs_several_title_hits():
    ok = verify_term("Zorn-Quill syndrome", fetch=fake_fetch(None, hits=3), wait_s=0)
    assert ok.status == "verified" and ok.method == "literature" and ok.id == "TERM:zorn-quill-syndrome"
    assert "not as an established diagnosis" in ok.reason
    few = verify_term("Zorn-Quill syndrome", fetch=fake_fetch(None, hits=1), wait_s=0)
    assert few.status == "not_verified" and "only 1" in few.reason


def test_nonsense_and_non_condition_words_are_not_verified_and_cost_no_literature_search():
    f = fake_fetch(None, hits=500)
    v = verify_term("flight of the buffalo", fetch=f, wait_s=0)
    assert v.status == "not_verified" and not any("europepmc" in u for u in f.calls)


def test_a_service_outage_is_reported_as_unavailable_not_as_not_a_term():
    assert verify_term("seizures", fetch=fake_fetch(SEIZURES, fail="esearch"), wait_s=0).status == "unavailable"
    assert verify_term("x syndrome", fetch=fake_fetch(None, fail="europepmc"), wait_s=0).status == "unavailable"


def test_the_store_adds_once_survives_a_restart_and_finds_by_synonym(tmp_path):
    v = verify_term("seizures", fetch=fake_fetch(SEIZURES, hits=2), wait_s=0)
    store = TermStore(tmp_path)
    row, persisted = store.add(v, asked="seizures")
    again, _ = store.add(v, asked="Seizure")
    assert persisted and again["id"] == row["id"] and len(store.all()) == 1
    assert [r["id"] for r in TermStore(tmp_path).find("fits")] == ["MESH:D012640"]
    assert row["review_state"] == "unreviewed" and row["source_url"].endswith("ui=D012640")


def test_only_a_verified_term_can_be_stored(tmp_path):
    bad = verify_term("flight of the buffalo", fetch=fake_fetch(None), wait_s=0)
    with pytest.raises(ValueError):
        TermStore(tmp_path).add(bad, asked="x")


def test_an_unwritable_store_keeps_the_term_in_memory_and_says_so(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")  # a file where the directory should be
    store = TermStore(blocker)
    row, persisted = store.add(verify_term("seizures", fetch=fake_fetch(SEIZURES), wait_s=0), asked="seizures")
    assert persisted is False and store.get(row["id"]) is not None
