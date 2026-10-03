"""Global search tests. The mini ontology below is SYNTHETIC (format-valid placeholder IDs);
the real-file test skips when scripts/fetch_ontologies.py has not been run."""

from pathlib import Path

import pytest

from atlas.resolver import DISEASE, GENE, PHENOTYPE, TIER_EXACT, TIER_RELATED, Resolver
from atlas.search import NON_HUMAN_ROOT, SearchIndex

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


@pytest.fixture
def ix() -> SearchIndex:
    r = Resolver()
    r.add(DISEASE, "MONDO:9000001", "Example disease type C", [("EDC", TIER_EXACT), ("XYZ", TIER_RELATED)],
          ["OMIM:900001"])
    r.add(DISEASE, "MONDO:9000002", "Other carcinoma", [("XYZ", TIER_EXACT)])
    r.add(DISEASE, "MONDO:9000003", "Example disease, animal", [])
    r.add(DISEASE, NON_HUMAN_ROOT, "non-human animal disease", [])
    r.add(GENE, "HGNC:900001", "EXG1", [("example gene 1", TIER_EXACT)])
    r.add(PHENOTYPE, "HP:9000001", "Seizure", [("Seizures", TIER_EXACT)])
    g2d = [{"gene_symbol": "EXG1", "association_type": "MENDELIAN", "disease_id": "OMIM:900001"}]
    parents = {"MONDO:9000003": {NON_HUMAN_ROOT}}
    return SearchIndex(r, None, g2d, parents)


def ids(res):
    return [h["id"] for h in res["results"]]


def test_all_words_match_finds_label_with_extra_words(ix):
    res = ix.search("example type C")
    assert ids(res)[0] == "MONDO:9000001"
    assert res["results"][0]["match"] == "all words"


def test_exact_synonym_beats_partial_and_says_what_matched(ix):
    h = ix.search("seizures")["results"][0]
    assert (h["id"], h["match"], h["matched"]) == ("HP:9000001", "exact synonym", "Seizures")


def test_shared_name_is_ambiguous_and_keeps_every_candidate(ix):
    res = ix.search("XYZ")
    assert res["ambiguous"] is True
    assert {"MONDO:9000001", "MONDO:9000002"} <= set(ids(res))


def test_close_spelling_is_a_suggestion_not_a_resolution(ix):
    res = ix.search("Seizurez")
    assert res["results"] and all(h["match"] == "close spelling" for h in res["results"])


def test_short_query_matches_name_starts(ix):
    res = ix.search("ex")
    assert "HGNC:900001" in ids(res) and all(h["match"] in ("starts with", "label") for h in res["results"])


def test_identifier_lookup(ix):
    assert ix.search("HGNC:900001")["results"][0]["match"] == "identifier"


def test_non_human_diseases_are_left_out(ix):
    assert "MONDO:9000003" not in ids(ix.search("example disease"))


def test_gene_and_disease_link_both_ways_with_source(ix):
    g = ix.related("HGNC:900001")["groups"][0]
    assert g["items"][0]["id"] == "MONDO:9000001" and "genes_to_disease" in g["source"]
    d = ix.related("MONDO:9000001")["groups"][0]
    assert d["items"][0]["id"] == "HGNC:900001"


def test_unknown_entry_has_no_related_groups(ix):
    assert ix.related("MONDO:9999999")["groups"] == []


@pytest.mark.skipif(not (RAW / "mondo" / "mondo.json").exists(), reason="pinned ontology files not downloaded")
def test_real_files_natural_phrasings():
    real = SearchIndex.from_raw(RAW)
    assert ids(real.search("Niemann-Pick type C"))[0] == "MONDO:0018982"
    assert real.search("NPC")["ambiguous"] is True
    assert ids(real.search("CLN3"))[0] == "HGNC:2074"
    assert not any(h["label"].endswith(", dog") for h in real.search("lysosomal storage disease")["results"])
