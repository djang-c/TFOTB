"""Hypothesis generation tests with a fake model. Claims are SYNTHETIC fixtures (software behaviour only)."""

from tests.conftest import make_claim

from atlas.hypotheses import HypothesisOutput, ProposedHypothesis, generate_hypotheses
from atlas.llm.base import LLMResult
from atlas.store import PublicStore

A, B, C = "MONDO:0000001", "MONDO:0000002", "MONDO:0000003"
GO = "GO:0005764"


class Fake:
    provider = "fake"

    def __init__(self, *hyps):
        self.hyps, self.calls, self.seen = list(hyps), 0, ""

    def parse(self, schema, **kw):
        self.calls += 1
        self.seen = kw["input_text"]
        return LLMResult(HypothesisOutput(hypotheses=self.hyps), "fake", "fake-model", kw["prompt_version"])


def store(**kw):
    s = PublicStore()
    for cid, d in (("CLAIM:a", A), ("CLAIM:b", B)):
        s.add(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id=GO, source_type="published", **kw))
    return s


def hyp(**kw):
    base = dict(
        subject_id=A, predicate="SHARES_PATHOGENIC_PATHWAY_WITH", object_id=B,
        supporting_claim_ids=["CLAIM:a", "CLAIM:b"],
        rationale="Both diseases accumulate material in the lysosome, so a shared lysosomal pathway is plausible; test it.",
    )
    return ProposedHypothesis(**{**base, **kw})


def run(*hyps, s=None):
    s = s or store()
    client = Fake(*hyps)
    return generate_hypotheses(client, s.claims), client


def test_grounded_hypothesis_is_stored_as_an_unreviewed_ai_inference_citing_stored_claims():
    rep, _ = run(hyp())
    c = rep.claims[0]
    assert (c.status.value, c.source_type.value, c.review_state.value) == ("inference", "ai_generated", "unreviewed")
    assert c.derived_from == ("CLAIM:a", "CLAIM:b") and c.source_span.startswith("AI hypothesis:")
    assert c.claim_id.startswith("CLAIM:HYP-") and c.extraction_method == "llm:fake-model@hypothesis-v1"


def test_a_citation_that_is_not_stored_is_rejected_so_citations_cannot_be_invented():
    rep, _ = run(hyp(supporting_claim_ids=["CLAIM:a", "CLAIM:invented"]))
    assert not rep.claims and "not stored" in rep.rejected[0]["reason"]


def test_one_supporting_claim_is_not_enough():
    rep, _ = run(hyp(supporting_claim_ids=["CLAIM:a"]))
    assert not rep.claims and "at least two" in rep.rejected[0]["reason"]


def test_a_model_cannot_introduce_an_entity_the_cited_claims_do_not_mention():
    rep, _ = run(hyp(object_id=C))
    assert not rep.claims and "not found in the cited claims" in rep.rejected[0]["reason"]


def test_hypotheses_cannot_rest_on_other_hypotheses_uploads_or_fixtures():
    s = store()
    s.add(make_claim("CLAIM:h", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=A, object_id=C, status="inference", source_type="published"))
    s.add(make_claim("CLAIM:u", "ACCUMULATES_IN_COMPARTMENT", subject_id=C, object_id=GO, source_type="lab_reported"))
    for bad in ("CLAIM:h", "CLAIM:u"):
        rep, _ = run(hyp(object_id=C, supporting_claim_ids=["CLAIM:a", bad]), s=s)
        assert not rep.claims and "credible sources" in rep.rejected[0]["reason"]


def test_prompt_only_shows_credible_observations_and_carries_citations():
    s = store()
    s.add(make_claim("CLAIM:u", "ACCUMULATES_IN_COMPARTMENT", subject_id=C, object_id=GO, source_type="lab_reported"))
    _, client = run(hyp(), s=s)
    assert "[CLAIM:a]" in client.seen and "CLAIM:u" not in client.seen


def test_no_credible_claims_means_no_model_call():
    rep, client = run(s=PublicStore())
    assert not rep.claims and client.calls == 0


def test_wrong_entity_types_duplicates_and_clinical_wording_are_rejected():
    assert "do not fit" in run(hyp(predicate="CANDIDATE_THERAPY_FOR"))[0].rejected[0]["reason"]
    assert "same entity" in run(hyp(object_id=A))[0].rejected[0]["reason"]
    assert "clinical" in run(hyp(rationale="Patients should take 5 mg daily of this compound."))[0].rejected[0]["reason"]
    s = store()
    s.add(make_claim("CLAIM:old", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=B, object_id=A, status="inference", source_type="published"))
    assert run(hyp(), s=s)[0].rejected[0]["reason"] == "already stored"


def test_same_hypothesis_proposed_twice_is_stored_once():
    rep, _ = run(hyp(), hyp())
    assert len(rep.claims) == 1 and rep.rejected[0]["reason"] == "duplicate hypothesis"


def test_adding_a_hypothesis_changes_no_evidence_category():
    from atlas.channels.base import ChannelRegistry
    from atlas.channels.claims import build_claim_channels
    from atlas.connections import run_query

    def cats(st):
        reg = ChannelRegistry()
        for ch in build_claim_channels(st):
            reg.register(ch)
        return [(r.result.candidate_id, r.result.category) for r in run_query(A, reg, st.claims, dataset_version="t", per_source=[]).ranked]

    s = store()
    before = cats(s)
    for c in run(hyp(), s=s)[0].claims:
        s.add(c)
    assert dict(cats(s)) == dict(before)
