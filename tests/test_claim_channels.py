"""T07/T08 claim channels. All claims are SYNTHETIC test fixtures."""

import pytest
from tests.conftest import make_claim

from atlas.channels.claims import build_claim_channels
from atlas.ranking import build_result
from atlas.schemas import EvidenceCategory
from atlas.store import PublicStore

Q, C, D = "MONDO:0000001", "MONDO:0000002", "MONDO:0000003"


@pytest.fixture()
def store():
    return PublicStore()


def chan(store, channel_id):
    return next(c for c in build_claim_channels(store) if c.channel_id == channel_id)


def test_no_claims_means_missing_not_zero(store):
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.availability.value == "missing" and out.score is None
    assert out.missing_fields == [f"claims:{Q}", f"claims:{C}"]


def test_one_side_without_claims_is_missing(store):
    store.add(make_claim("CLAIM:a", "PERTURBS_MECHANISM", subject_id=Q, object_id="GO:0000001"))
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.availability.value == "missing" and out.missing_fields == [f"claims:{C}"]


def test_shared_feature_is_supported_by_claims_from_both_sides(store):
    store.add(make_claim("CLAIM:a", "ACCUMULATES_IN_COMPARTMENT", subject_id=Q, object_id="GO:0005764", lineage="STUDY:s1"))
    store.add(make_claim("CLAIM:b", "ACCUMULATES_IN_COMPARTMENT", subject_id=C, object_id="GO:0005764", lineage="STUDY:s1"))
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.availability.value == "available" and out.supporting_claim_ids == ["CLAIM:a", "CLAIM:b"]
    # same study on both sides: counts once toward independence
    res = build_result(Q, C, [out], store.claims)
    assert res.category is EvidenceCategory.hypothesis_only  # unreviewed


def test_direct_hypothesis_claim_never_reaches_reviewed_lead(store):
    store.add(
        make_claim("CLAIM:h", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=Q, object_id=C, status="inference", review_state="reviewed")
    )
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.supporting_claim_ids == ["CLAIM:h"]
    assert build_result(Q, C, [out], store.claims).category is EvidenceCategory.hypothesis_only


def test_opposite_direction_blocks_shared_treatment(store):
    store.add(make_claim("CLAIM:a", "PERTURBS_MECHANISM", subject_id=Q, object_id="GO:0000001", context={"direction": "up"}))
    store.add(make_claim("CLAIM:b", "PERTURBS_MECHANISM", subject_id=C, object_id="GO:0000001", context={"direction": "down"}))
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.context_mismatches == ["effect_direction"]
    assert build_result(Q, C, [out], store.claims).shared_treatment_inference_allowed is False


def test_same_gene_is_reported_but_never_supports_a_mechanism(store):
    store.add(make_claim("CLAIM:g1", "GENE_ASSOCIATED_WITH_DISEASE", subject_id="HGNC:2074", object_id=Q))
    store.add(make_claim("CLAIM:g2", "GENE_ASSOCIATED_WITH_DISEASE", subject_id="HGNC:2074", object_id=C))
    out = chan(store, "dna_variants").compare(Q, C, {})
    assert out.availability.value == "available" and out.supporting_claim_ids == []
    assert "shared HGNC:2074" in out.context_matches and any("not variant-level" in x for x in out.limitations)
    assert build_result(Q, C, [out], store.claims).category is EvidenceCategory.hypothesis_only


def test_predicted_rna_effect_is_not_support(store):
    store.add(make_claim("CLAIM:o", "HAS_OBSERVED_RNA_EFFECT", subject_id=Q, object_id="HGNC:100"))
    store.add(make_claim("CLAIM:p", "HAS_PREDICTED_RNA_EFFECT", subject_id=C, object_id="HGNC:100", status="computational_prediction"))
    out = chan(store, "rna_effects").compare(Q, C, {})
    assert out.supporting_claim_ids == ["CLAIM:o"]
    assert any("predicted, not observed" in x for x in out.limitations)


def test_tissue_mismatch_is_kept_as_a_caveat(store):
    store.add(make_claim("CLAIM:a", "HAS_OBSERVED_RNA_EFFECT", subject_id=Q, object_id="HGNC:100", context={"tissue": "brain"}))
    store.add(make_claim("CLAIM:b", "HAS_OBSERVED_RNA_EFFECT", subject_id=C, object_id="HGNC:100", context={"tissue": "liver"}))
    assert chan(store, "rna_effects").compare(Q, C, {}).context_mismatches == ["tissue"]


def test_both_sides_have_claims_but_nothing_shared(store):
    store.add(make_claim("CLAIM:a", "PERTURBS_MECHANISM", subject_id=Q, object_id="GO:0000001"))
    store.add(make_claim("CLAIM:b", "PERTURBS_MECHANISM", subject_id=C, object_id="GO:0000002"))
    out = chan(store, "molecular_mechanisms").compare(Q, C, {})
    assert out.availability.value == "available" and out.supporting_claim_ids == []
    assert any("share no feature" in x for x in out.limitations)


def test_candidates_are_diseases_sharing_a_feature_with_the_query(store):
    store.add(make_claim("CLAIM:a", "PERTURBS_MECHANISM", subject_id=Q, object_id="GO:0000001"))
    store.add(make_claim("CLAIM:b", "PERTURBS_MECHANISM", subject_id=C, object_id="GO:0000001"))
    store.add(make_claim("CLAIM:c", "PERTURBS_MECHANISM", subject_id=D, object_id="GO:0000009"))
    assert chan(store, "molecular_mechanisms").retrieve_candidates(Q, {}) == [C]


def test_same_compartment_with_different_substances_is_not_a_shared_feature(store):
    store.add(make_claim("CLAIM:a", "ACCUMULATES_IN_COMPARTMENT", subject_id=Q, object_id="GO:0005764", context={"substance": "CHEBI:16113"}))
    store.add(make_claim("CLAIM:b", "ACCUMULATES_IN_COMPARTMENT", subject_id=C, object_id="GO:0005764", context={"substance": "CHEBI:99999"}))
    ch = chan(store, "molecular_mechanisms")
    out = ch.compare(Q, C, {})
    assert out.availability.value == "available" and out.supporting_claim_ids == []
    assert any("share no feature" in x for x in out.limitations)
    assert ch.retrieve_candidates(Q, {}) == []


def test_same_compartment_and_same_substance_is_shared(store):
    for cid, d in (("CLAIM:a", Q), ("CLAIM:b", C)):
        store.add(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id="GO:0005764", context={"substance": "CHEBI:16113"}))
    ch = chan(store, "molecular_mechanisms")
    out = ch.compare(Q, C, {})
    assert out.supporting_claim_ids == ["CLAIM:a", "CLAIM:b"] and out.context_matches == ["shared GO:0005764[CHEBI:16113]"]
    assert ch.retrieve_candidates(Q, {}) == [C]


def _share(store, cid, disease, direction, lineage):
    from tests.conftest import make_claim

    store.add(make_claim(cid, "PERTURBS_MECHANISM", subject_id=disease, object_id="GO:0005764", source_type="published",
                         lineage=lineage, context={"direction": direction}))


def _query(store):
    from datetime import UTC, datetime

    from atlas.channels.base import ChannelRegistry
    from atlas.connections import run_query

    reg = ChannelRegistry()
    for ch in build_claim_channels(store):
        reg.register(ch)
    return run_query("MONDO:0000001", reg, store.claims, dataset_version="t", per_source=[], now=datetime(2026, 10, 3, tzinfo=UTC))


def test_opposing_directions_on_a_shared_feature_are_a_visible_contradiction_end_to_end():
    from atlas.schemas import EvidenceCategory

    store = PublicStore()
    _share(store, "CLAIM:q", "MONDO:0000001", "increased", "STUDY:q")
    _share(store, "CLAIM:a", "MONDO:0000002", "down-regulated", "STUDY:a")
    res = _query(store).ranked[0].result
    assert res.category is EvidenceCategory.conflicting_evidence
    assert not res.shared_treatment_inference_allowed
    comp = next(c for c in res.comparisons if c.channel_id == "molecular_mechanisms")
    assert set(comp.contradicting_claim_ids) == {"CLAIM:q", "CLAIM:a"} and "effect_direction" in comp.context_mismatches


def test_different_wordings_of_the_same_direction_are_not_a_contradiction():
    store = PublicStore()
    _share(store, "CLAIM:q", "MONDO:0000001", "increased", "STUDY:q")
    _share(store, "CLAIM:a", "MONDO:0000002", "upregulated", "STUDY:a")
    comp = next(c for c in _query(store).ranked[0].result.comparisons if c.channel_id == "molecular_mechanisms")
    assert not comp.contradicting_claim_ids and "effect_direction" not in comp.context_mismatches


def test_an_unclear_direction_is_neither_agreement_nor_contradiction():
    store = PublicStore()
    _share(store, "CLAIM:q", "MONDO:0000001", "changed", "STUDY:q")
    _share(store, "CLAIM:a", "MONDO:0000002", "decreased", "STUDY:a")
    comp = next(c for c in _query(store).ranked[0].result.comparisons if c.channel_id == "molecular_mechanisms")
    assert not comp.contradicting_claim_ids


def test_a_claim_that_names_a_contradicting_claim_is_reported_as_a_contradiction():
    from tests.conftest import make_claim

    store = PublicStore()
    _share(store, "CLAIM:q", "MONDO:0000001", None, "STUDY:q")
    store.add(make_claim("CLAIM:a", "PERTURBS_MECHANISM", subject_id="MONDO:0000002", object_id="GO:0005764",
                         source_type="published", lineage="STUDY:a", contradicts=("CLAIM:q",)))
    comp = next(c for c in _query(store).ranked[0].result.comparisons if c.channel_id == "molecular_mechanisms")
    assert set(comp.contradicting_claim_ids) == {"CLAIM:a", "CLAIM:q"}
