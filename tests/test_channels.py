from atlas.channels import ChannelRegistry, EvidenceChannel
from atlas.ranking import build_result
from atlas.schemas import ChannelComparison


class TestOnlyChannel(EvidenceChannel):
    channel_id, version = "test_only", "0"

    def retrieve_candidates(self, query_id, context):
        return ["MONDO:0000002"]

    def compare(self, query_id, candidate_id, context):
        return ChannelComparison(
            channel_id=self.channel_id,
            channel_version=self.version,
            query_id=query_id,
            candidate_id=candidate_id,
            availability="missing",
            missing_fields=["everything"],
        )


class Boom(TestOnlyChannel):
    channel_id = "boom"

    def compare(self, *a):
        raise RuntimeError("source down")


def test_new_channel_registers_without_core_changes():
    reg = ChannelRegistry()
    reg.register(TestOnlyChannel())
    cands = reg.candidate_union("MONDO:0000001", {})
    res = build_result(
        "MONDO:0000001", cands[0], reg.compare_all("MONDO:0000001", cands[0], {}), {}
    )
    assert res.comparisons[0].channel_id == "test_only"
    assert res.category.value == "insufficient coverage"


def test_failing_channel_is_reported_not_hidden():
    reg = ChannelRegistry()
    reg.register(TestOnlyChannel())
    reg.register(Boom())
    out = reg.compare_all("q", "MONDO:0000002", {})
    assert {c.channel_id: c.availability.value for c in out} == {
        "test_only": "missing",
        "boom": "failed",
    }


def test_a_new_available_mechanism_channel_makes_a_lead_without_editing_ranking():
    """Audit D-F1: the old extensibility test used a channel that was always missing, so it proved nothing."""
    from tests.conftest import make_claim

    from atlas.channels.base import ChannelRegistry, EvidenceChannel
    from atlas.connections import run_query
    from atlas.schemas import ChannelComparison, EvidenceCategory

    claim = make_claim("CLAIM:p", "PERTURBS_MECHANISM", source_type="published", review_state="reviewed")

    class Proteomics(EvidenceChannel):
        channel_id, version, kind = "proteomics_test_only", "1", "mechanism"

        def retrieve_candidates(self, query_id, context):
            return ["MONDO:0000002"]

        def compare(self, query_id, candidate_id, context):
            return ChannelComparison(
                channel_id=self.channel_id, channel_version="1", query_id=query_id, candidate_id=candidate_id,
                availability="available", supporting_claim_ids=["CLAIM:p"],
            )

    reg = ChannelRegistry()
    reg.register(Proteomics())
    out = run_query("MONDO:0000001", reg, {"CLAIM:p": claim}, dataset_version="t", per_source=[])
    assert out.ranked[0].result.category is EvidenceCategory.reviewed_mechanistic_lead

    class Quiet(Proteomics):
        channel_id, kind = "context_test_only", "context"

    reg2 = ChannelRegistry()
    reg2.register(Quiet())
    out2 = run_query("MONDO:0000001", reg2, {"CLAIM:p": claim}, dataset_version="t", per_source=[])
    assert out2.ranked[0].result.category is EvidenceCategory.hypothesis_only  # a context channel never makes a lead
