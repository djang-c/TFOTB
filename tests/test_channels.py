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
