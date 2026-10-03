import pytest
from pydantic import ValidationError

from atlas.schemas import Availability, ChannelComparison, validate_curie


def test_namespace_shaped_id_from_label_is_rejected():
    with pytest.raises(ValueError):
        validate_curie("HGNC:GBA1")  # symbol appended to prefix is not an HGNC ID
    assert validate_curie("HGNC:1234") == "HGNC:1234"


def test_unknown_predicate_rejected(mk):
    with pytest.raises(ValidationError):
        mk(pred="CURES")


def test_strong_causal_cannot_rest_on_inference(mk):
    with pytest.raises(ValidationError):
        mk(status="inference")  # default predicate is PERTURBS_MECHANISM


def test_score_requires_definition(mk):
    with pytest.raises(ValidationError):
        mk(score=0.9)


def test_missing_channel_must_have_null_score():
    with pytest.raises(ValidationError):
        ChannelComparison(
            channel_id="rna_effects",
            channel_version="1",
            query_id="q",
            candidate_id="c",
            availability=Availability.missing,
            score=0.0,
            score_definition="x",
        )


def test_new_predicates_are_accepted(mk):
    assert mk(pred="GENE_ASSOCIATED_WITH_DISEASE", subject_id="HGNC:2074", object_id="MONDO:0000001")
    assert mk(pred="ACCUMULATES_IN_COMPARTMENT", object_id="GO:0005764")


@pytest.mark.parametrize("pred", ["SHARES_PATHOGENIC_PATHWAY_WITH", "CANDIDATE_THERAPY_FOR"])
def test_hypothesis_only_predicates_cannot_be_observations(mk, pred):
    with pytest.raises(ValidationError):
        mk(pred=pred, status="reported_observation")
    assert mk(pred=pred, status="inference").status.value == "inference"
