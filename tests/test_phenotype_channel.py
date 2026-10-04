"""T06 tests. Ontology and annotations below are SYNTHETIC; real-file tests skip if data is absent."""

from pathlib import Path

import pytest

from atlas.channels.phenotype import PhenotypeChannel
from atlas.resolver import Resolver

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
H = "HP:000000"


@pytest.fixture()
def ch() -> PhenotypeChannel:
    parents = {f"{H}2": {f"{H}1"}, f"{H}3": {f"{H}2"}, f"{H}4": {f"{H}2"}, f"{H}5": {f"{H}1"}}
    labels = {f"{H}{i}": f"synthetic term {i}" for i in range(1, 6)}
    terms = {
        "OMIM:1": {f"{H}3"},
        "OMIM:2": {f"{H}4"},
        "OMIM:3": {f"{H}5"},
        "OMIM:4": {f"{H}3", f"{H}5"},
        "OMIM:5": {f"{H}5"},
        "OMIM:6": {f"{H}5"},
        "OMIM:7": {f"{H}5"},
        "OMIM:8": {f"{H}5"},
        "OMIM:9": {f"{H}5"},
        "OMIM:10": {f"{H}5"},
        "OMIM:99": {f"{H}5"},  # has no MONDO mapping
    }
    absent = {"OMIM:2": {f"{H}3"}}
    xref = {f"OMIM:{i}": {f"MONDO:000000{i}"} for i in range(1, 5)}
    return PhenotypeChannel(parents, labels, terms, absent, xref, "SYNTHETIC HPO test version")


Q = "MONDO:0000001"


def test_ic_child_is_at_least_parent(ch):
    assert ch.ic(f"{H}3") >= ch.ic(f"{H}2") >= ch.ic(f"{H}1") == 0.0


def test_lin_self_is_one_and_symmetric_in_range(ch):
    terms = [f"{H}{i}" for i in range(1, 6)]
    for a in terms[1:]:
        assert ch.lin(a, a) == 1.0
        for b in terms:
            assert ch.lin(a, b) == pytest.approx(ch.lin(b, a))
            assert 0.0 <= ch.lin(a, b) <= 1.0


def test_bma_is_symmetric_bounded_and_self_is_one(ch):
    a, b = {f"{H}3"}, {f"{H}4", f"{H}5"}
    assert ch.bma_lin(a, b) == pytest.approx(ch.bma_lin(b, a))
    assert 0.0 <= ch.bma_lin(a, b) <= 1.0
    assert ch.bma_lin(a, a) == pytest.approx(1.0)


def test_specific_terms_avoid_ancestor_double_counting(ch):
    assert ch.specific({f"{H}2", f"{H}3"}) == {f"{H}3"}


def test_similar_diseases_score_higher_than_unrelated(ch):
    near = ch.compare(Q, "MONDO:0000002", {})  # sibling terms under the same parent
    far = ch.compare(Q, "MONDO:0000003", {})  # different branch
    assert near.availability.value == far.availability.value == "available"
    assert near.score > far.score
    assert "SYNTHETIC HPO test version" in near.score_definition


def test_missing_annotations_are_missing_not_zero(ch):
    out = ch.compare(Q, "MONDO:0000777", {})
    assert out.availability.value == "missing" and out.score is None
    assert out.missing_fields == ["hpo_annotations:MONDO:0000777"]


def test_explicitly_absent_term_is_not_a_match_and_is_reported(ch):
    out = ch.compare(Q, "MONDO:0000002", {})
    assert any("explicitly absent" in lim for lim in out.limitations)
    # unknown (not mentioned) must not be reported as absent
    assert not any("explicitly absent" in lim for lim in ch.compare(Q, "MONDO:0000003", {}).limitations)


def test_unmapped_sources_are_disclosed(ch):
    assert any("could not be mapped" in lim for lim in ch.compare(Q, "MONDO:0000002", {}).limitations)


def test_candidates_exclude_the_query_and_are_deterministic(ch):
    first = ch.retrieve_candidates(Q, {})
    assert Q not in first and first == ch.retrieve_candidates(Q, {})
    assert ch.retrieve_candidates("MONDO:0000777", {}) == []


@pytest.fixture(scope="module")
def real():
    return PhenotypeChannel.from_raw(RAW, Resolver.from_raw(RAW))


@pytest.mark.skipif(not (RAW / "hpo" / "phenotype.hpoa").exists(), reason="pinned ontology files not downloaded")
class TestRealFiles:
    def test_seed_pair_compares_with_defined_score(self, real):
        out = real.compare("MONDO:0008767", "MONDO:0018982", {})  # CLN3 disease vs Niemann-Pick type C
        assert out.availability.value in {"available", "missing"}
        if out.availability.value == "available":
            assert 0.0 <= out.score <= 1.0 and "annotated source diseases" in out.score_definition


# --- symptoms-only ranking (audit D/E: the "no disease named" input) --------------------------------
def test_symptom_ranking_orders_by_weighted_coverage_then_profile_share_and_explains_both(ch):
    rows = ch.rank_by_symptoms([f"{H}3", f"{H}5"])
    by = {r["disease_id"]: r for r in rows}
    # MONDO:4 records both described symptoms, so it covers everything described (coverage 1.0)
    assert by["MONDO:0000004"]["coverage"] == 1.0 and by["MONDO:0000004"]["unmatched"] == []
    assert rows[0]["disease_id"] == "MONDO:0000004"
    assert by["MONDO:0000001"]["unmatched"] == [f"{H}5"]  # a partial match says what it does not cover
    assert "not probabilities" in ch.SYMPTOM_DEFINITION and "profile_share" in ch.SYMPTOM_DEFINITION


def test_a_more_specific_recorded_form_of_a_symptom_counts_as_a_match(ch):
    # H3 is_a H2 is_a H1: asking for the parent finds diseases recorded with the more specific child
    assert "MONDO:0000001" in {r["disease_id"] for r in ch.rank_by_symptoms([f"{H}2"])}


def test_recorded_absence_flows_down_to_specific_forms_but_never_up_to_the_general_symptom():
    parents = {f"{H}3": {f"{H}2"}, f"{H}2": {f"{H}1"}}
    labels = {f"{H}{i}": f"synthetic term {i}" for i in (1, 2, 3)}
    terms = {"OMIM:1": {f"{H}3"}, "OMIM:2": {f"{H}3"}, "OMIM:3": {f"{H}2"}}
    absent = {"OMIM:2": {f"{H}2"}, "OMIM:3": {f"{H}3"}}  # D2: general H2 absent; D3: only the specific H3 absent
    xref = {f"OMIM:{i}": {f"MONDO:000000{i}"} for i in (1, 2, 3)}
    c = PhenotypeChannel(parents, labels, terms, absent, xref, "SYNTHETIC HPO test version")
    by = {r["disease_id"]: r for r in c.rank_by_symptoms([f"{H}3"])}
    assert by["MONDO:0000002"]["recorded_absent"] == [f"{H}3"]  # general symptom absent => the specific form is too
    rows = c.rank_by_symptoms([f"{H}3"])
    assert [r["disease_id"] for r in rows].index("MONDO:0000002") > [r["disease_id"] for r in rows].index("MONDO:0000001")
    d3 = {r["disease_id"]: r for r in c.rank_by_symptoms([f"{H}2"])}["MONDO:0000003"]
    assert d3["recorded_absent"] == []  # a specific form being absent does not make the general symptom absent


def test_unknown_terms_give_no_candidates_not_a_guess(ch):
    assert ch.rank_by_symptoms(["HP:9999999"]) == [] and ch.rank_by_symptoms([]) == []


def test_symptom_ranking_respects_the_limit_and_the_exclusion_set(ch):
    assert len(ch.rank_by_symptoms([f"{H}5"], limit=2)) == 2
    assert "MONDO:0000003" not in {r["disease_id"] for r in ch.rank_by_symptoms([f"{H}5"], exclude={"MONDO:0000003"})}
