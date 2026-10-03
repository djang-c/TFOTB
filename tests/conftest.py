"""SYNTHETIC fixtures for software-behavior tests only. IDs are format-valid placeholders and
make NO biological claim. Real biological fixtures need cited expert review (PLAN: T01)."""

import pytest

from atlas.schemas import Claim


def make_claim(cid="CLAIM:c1", pred="PERTURBS_MECHANISM", lineage="STUDY:s1", **kw):
    base = dict(
        claim_id=cid,
        subject_id="MONDO:0000001",
        predicate=pred,
        object_id="HP:0000001",
        source_url="https://example.invalid/synthetic",
        source_span="synthetic span",
        source_type="synthetic_fixture",
        status="reported_observation",
        lineage_id=lineage,
    )
    base.update(kw)
    return Claim(**base)


@pytest.fixture
def mk():
    return make_claim
