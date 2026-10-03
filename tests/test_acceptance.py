"""T13 acceptance tests from PLAN section on evaluation: assay incompatibility, honest gap,
action traceability. Claims, sources and channels are SYNTHETIC fixtures (software behaviour only)."""

from datetime import UTC, datetime

import pytest
from tests.conftest import make_claim

from atlas.cards import evidence_brief, gap_followup
from atlas.channels.base import ChannelRegistry
from atlas.channels.claims import build_claim_channels
from atlas.connections import run_query
from atlas.schemas import ActionCard, SourceCoverage, SourceStatus
from atlas.store import PublicStore

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
Q, A = "MONDO:0000001", "MONDO:0000002"


def _run(store, per_source=()):
    reg = ChannelRegistry()
    for ch in build_claim_channels(store):
        reg.register(ch)
    return run_query(Q, reg, store.claims, dataset_version="t", per_source=list(per_source), now=NOW)


def _shared(store, ctx_q=None, ctx_a=None):
    for cid, d, ctx in (("CLAIM:q", Q, ctx_q or {}), ("CLAIM:a", A, ctx_a or {})):
        store.add(
            make_claim(
                cid, "PERTURBS_MECHANISM", subject_id=d, object_id="HP:0000118", lineage=f"STUDY:{cid}", context=ctx
            )
        )


# --- Assay incompatibility -------------------------------------------------------------------
def test_unlike_assays_are_flagged_and_no_number_is_pooled():
    store = PublicStore()
    _shared(store, {"assay": "western blot"}, {"assay": "mass spectrometry"})
    result = _run(store).ranked[0].result
    assert any(f.endswith(":assay") for f in result.compatibility_flags)
    assert all(c.score is None for c in result.comparisons)  # nothing pooled or averaged


def test_like_assays_raise_no_assay_flag():
    store = PublicStore()
    _shared(store, {"assay": "western blot"}, {"assay": "western blot"})
    assert not any(f.endswith(":assay") for f in _run(store).ranked[0].result.compatibility_flags)


def test_an_assay_missing_on_one_side_is_not_called_a_mismatch():
    store = PublicStore()
    _shared(store, {"assay": "western blot"}, {})
    assert not any(f.endswith(":assay") for f in _run(store).ranked[0].result.compatibility_flags)


# --- Honest gap -------------------------------------------------------------------------------
def test_gap_is_scoped_dated_lists_failed_sources_and_never_claims_global_absence():
    failed = SourceCoverage(source="PMID:1", status=SourceStatus.failed, error="not open access")
    out = _run(PublicStore(), per_source=[failed])
    gap = out.gap
    assert gap is not None and gap.failed_sources == ("PMID:1",)
    assert "indexed evidence as of 2026-10-03" in gap.statement and gap.missing_information
    assert gap.coverage_manifest_id == out.coverage.manifest_id
    text = gap_followup(gap, now=NOW).body_markdown.lower()
    assert "no connection exists" not in text and "does not exist" not in text and "proven" not in text
    assert "pmid:1" in text  # the failed source is disclosed


def test_a_failed_source_stays_visible_in_the_manifest_even_when_results_exist():
    store = PublicStore()
    _shared(store)
    failed = SourceCoverage(source="PMID:2", status=SourceStatus.failed, error="timeout")
    out = _run(store, per_source=[failed])
    assert [s.status for s in out.coverage.per_source] == [SourceStatus.failed]


# --- Action traceability ------------------------------------------------------------------------
def test_every_biological_line_in_a_card_maps_to_a_stored_claim_and_a_named_human():
    store = PublicStore()
    _shared(store)
    card = evidence_brief(_run(store), store.claims, now=NOW)
    bio = [line for line in card.body_markdown.splitlines() if "`PERTURBS_MECHANISM`" in line]
    assert bio and all("[^c:" in line for line in bio)
    assert set(card.claim_ids) <= set(store.claims) and card.responsible_human.strip()


def test_a_card_that_cites_a_claim_it_does_not_list_is_rejected():
    store = PublicStore()
    _shared(store)
    data = evidence_brief(_run(store), store.claims, now=NOW).model_dump()
    data["body_markdown"] += "\n- an extra statement [^c:CLAIM:not-listed]"
    with pytest.raises(ValueError, match="not in claim_ids"):
        ActionCard(**data)


def test_a_card_without_a_responsible_human_is_rejected():
    store = PublicStore()
    _shared(store)
    data = evidence_brief(_run(store), store.claims, now=NOW).model_dump()
    data["responsible_human"] = ""
    with pytest.raises(ValueError):
        ActionCard(**data)
