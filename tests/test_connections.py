"""T09 tests. Claims and channels are SYNTHETIC test fixtures."""

from datetime import UTC, datetime

from tests.conftest import make_claim

from atlas.channels.base import ChannelRegistry, EvidenceChannel
from atlas.channels.claims import build_claim_channels
from atlas.connections import run_query, sources_from_extraction_runs
from atlas.schemas import ChannelComparison, EvidenceCategory
from atlas.store import PublicStore

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
Q, A, B, C = "MONDO:0000001", "MONDO:0000002", "MONDO:0000003", "MONDO:0000004"


def registry(store):
    reg = ChannelRegistry()
    for ch in build_claim_channels(store):
        reg.register(ch)
    return reg


def run(store, reg=None, sources=()):
    return run_query(
        Q, reg or registry(store), store.claims, dataset_version="test-1", per_source=list(sources), now=NOW
    )


def share(store, cid, disease, feature="GO:0005764", **kw):
    store.add(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=disease, object_id=feature, **kw))


def test_no_candidates_gives_scoped_gap_and_empty_ranking():
    out = run(PublicStore())
    assert out.ranked == [] and out.gap.kind == "no_supported_route"
    assert "as of 2026-10-03" in out.gap.statement and out.gap.coverage_manifest_id == out.coverage.manifest_id


def test_hypothesis_only_results_produce_a_gap_naming_the_missing_expert():
    store = PublicStore()
    share(store, "CLAIM:q", Q)
    share(store, "CLAIM:a", A)
    out = run(store)
    assert out.ranked[0].result.category is EvidenceCategory.hypothesis_only
    assert out.gap.kind == "hypothesis_only" and "unassigned" in out.gap.reviewer_role
    assert set(out.gap.known_claim_ids) == {"CLAIM:q", "CLAIM:a"}


def test_reviewed_mechanism_has_no_gap():
    store = PublicStore()
    share(store, "CLAIM:q", Q, review_state="reviewed")
    share(store, "CLAIM:a", A, review_state="reviewed")
    out = run(store)
    assert out.ranked[0].result.category is EvidenceCategory.reviewed_mechanistic_lead and out.gap is None


def test_within_category_direct_then_reviewed_then_id_order():
    store = PublicStore()
    for cid, d in (("CLAIM:q", Q), ("CLAIM:a", A), ("CLAIM:b", B), ("CLAIM:c", C)):
        share(store, cid, d, lineage=f"STUDY:{cid}")
    # C is linked directly by a hypothesis claim; B has one reviewed supporting claim
    store.add(make_claim("CLAIM:d", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=Q, object_id=C, status="inference"))
    store.add(make_claim("CLAIM:r", "ACCUMULATES_IN_COMPARTMENT", subject_id=B, object_id="GO:0005764", review_state="reviewed", lineage="STUDY:r"))
    out = run(store)
    order = [r.result.candidate_id for r in out.ranked]
    assert order == [C, B, A]
    assert out.ranked[0].direct and not out.ranked[1].direct


def test_a_channel_number_never_reorders_results():
    class Scored(EvidenceChannel):
        channel_id, version = "phenotype", "1"

        def retrieve_candidates(self, query_id, context):
            return [A, B]

        def compare(self, query_id, candidate_id, context):
            return ChannelComparison(
                channel_id="phenotype", channel_version="1", query_id=query_id, candidate_id=candidate_id,
                availability="available", score=0.99 if candidate_id == B else 0.01, score_definition="test similarity",
            )

    reg = ChannelRegistry()
    reg.register(Scored())
    out = run(PublicStore(), reg)
    assert [r.result.candidate_id for r in out.ranked] == [A, B]  # ID order, not score order


def test_independent_lineages_count_shared_study_once():
    store = PublicStore()
    share(store, "CLAIM:q", Q, lineage="STUDY:same")
    share(store, "CLAIM:a", A, lineage="STUDY:same")
    assert run(store).ranked[0].independent_lineages == 1


def test_failed_channel_is_visible_in_coverage_and_does_not_hide_others():
    class Boom(EvidenceChannel):
        channel_id, version = "boom", "1"

        def retrieve_candidates(self, query_id, context):
            return [A]

        def compare(self, *a):
            raise RuntimeError("source down")

    reg = ChannelRegistry()
    reg.register(Boom())
    out = run(PublicStore(), reg)
    chans = {c.channel_id: c for c in out.coverage.per_channel}
    assert chans["boom"].availability.value == "failed" and "0 of 1" in chans["boom"].note


def test_coverage_manifest_is_deterministic_and_uses_recorded_counts():
    store = PublicStore()
    share(store, "CLAIM:q", Q)
    share(store, "CLAIM:a", A)
    runs = [
        {"source_id": "PMID:1", "status": "extracted", "reason": "", "prompt_version": "extract-v1",
         "claims_added": 2, "claims_already_present": 1, "statements_quarantined": 3},
        {"source_id": "PMID:2", "status": "not_extracted", "reason": "model refused: x", "prompt_version": "extract-v1",
         "claims_added": 0, "claims_already_present": 0, "statements_quarantined": 0},
    ]
    out1, out2 = run(store, sources=sources_from_extraction_runs(runs)), run(store, sources=sources_from_extraction_runs(runs))
    assert out1.coverage.manifest_id == out2.coverage.manifest_id and out1.coverage.manifest_id.startswith("COV:")
    ok, failed = out1.coverage.per_source
    assert (ok.fetched, ok.screened) == (6, 3) and failed.status.value == "failed"
    assert out1.gap.failed_sources == ("PMID:2",)
    assert out1.coverage.filters["candidates_considered"] == 1
