"""T10 card tests. Claims, assets and contacts are SYNTHETIC test fixtures."""

from datetime import UTC, date, datetime

import pytest
from tests.conftest import make_claim

from atlas.cards import CardError, asset_reuse, evidence_brief, gap_followup, outreach_note
from atlas.channels.base import ChannelRegistry
from atlas.channels.claims import build_claim_channels
from atlas.connections import run_query
from atlas.schemas import AssetKind, AssetResult, Contact
from atlas.store import PublicStore

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
Q, A = "MONDO:0000001", "MONDO:0000002"


def outcome(store):
    reg = ChannelRegistry()
    for ch in build_claim_channels(store):
        reg.register(ch)
    return run_query(Q, reg, store.claims, dataset_version="test-1", per_source=[], now=NOW)


def shared_store(**kw):
    store = PublicStore()
    for cid, d in (("CLAIM:q", Q), ("CLAIM:a", A)):
        store.add(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id="GO:0005764", **kw))
    return store


def asset(store, contact=True, **kw):
    store.add(make_claim("CLAIM:asset", "ASSET_RELEVANT_TO", subject_id="ASSET:synthetic-1", object_id=Q))
    base = dict(
        asset_id="ASSET:synthetic-1", asset_kind=AssetKind.registry, label="Synthetic registry",
        source_url="https://example.invalid/registry", relevance_claim_ids=("CLAIM:asset",),
        access_conditions="Request through the registry office.", reuse_limits=("adults only",),
        needs_expert_review=("confirm the age range",),
        contact=Contact(label="Registry office", url="https://example.invalid/contact",
                        source_url="https://example.invalid/registry", verified_at=date(2026, 10, 3)) if contact else None,
    )
    return AssetResult(**{**base, **kw})


def test_brief_cites_only_stored_claims_and_says_they_are_unreviewed():
    store = shared_store()
    card = evidence_brief(outcome(store), store.claims, now=NOW)
    assert card.kind == "evidence_brief" and set(card.claim_ids) == {"CLAIM:q", "CLAIM:a"}
    assert "[^c:CLAIM:q]" in card.body_markdown and "unreviewed" in card.body_markdown
    assert "hypothesis only" in card.body_markdown  # the evidence category, not an invented strength
    assert card.coverage_manifest_id.startswith("COV:") and "unassigned" in card.responsible_human


def test_brief_marks_inference_claims_as_hypothesis_only():
    store = shared_store()
    store.add(make_claim("CLAIM:h", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=Q, object_id=A, status="inference"))
    card = evidence_brief(outcome(store), store.claims, now=NOW)
    line = next(x for x in card.body_markdown.splitlines() if "[^c:CLAIM:h]" in x)
    assert "**hypothesis only**" in line and "inference, unreviewed" in line


def test_brief_with_no_candidates_is_still_a_valid_card_that_says_so():
    card = evidence_brief(outcome(PublicStore()), {}, now=NOW)
    assert "No connected candidates" in card.body_markdown and card.claim_ids == ()


def test_brief_uses_labels_when_given_and_ids_otherwise():
    store = shared_store()
    card = evidence_brief(outcome(store), store.claims, label_of=lambda i: {Q: "Disease One"}.get(i, ""), now=NOW)
    assert "Disease One (MONDO:0000001)" in card.body_markdown and "MONDO:0000002" in card.body_markdown


def test_brief_never_shows_a_score_without_its_definition_and_says_not_a_probability():
    from atlas.channels.base import EvidenceChannel
    from atlas.schemas import ChannelComparison

    class Scored(EvidenceChannel):
        channel_id, version = "phenotype", "1"

        def retrieve_candidates(self, query_id, context):
            return [A]

        def compare(self, query_id, candidate_id, context):
            return ChannelComparison(
                channel_id="phenotype", channel_version="1", query_id=query_id, candidate_id=candidate_id,
                availability="available", score=0.405, score_definition="test similarity",
            )

    reg = ChannelRegistry()
    reg.register(Scored())
    out = run_query(Q, reg, {}, dataset_version="t", per_source=[], now=NOW)
    body = evidence_brief(out, {}, now=NOW).body_markdown
    assert "similarity 0.405 (test similarity; not a probability)" in body


def test_card_ids_are_deterministic():
    store = shared_store()
    a = evidence_brief(outcome(store), store.claims, now=NOW)
    b = evidence_brief(outcome(store), store.claims, now=NOW)
    assert a.card_id == b.card_id and a.card_id.startswith("CARD:")


def test_gap_card_is_scoped_dated_and_names_the_reviewer():
    out = outcome(PublicStore())
    card = gap_followup(out.gap, label_of=lambda i: "Disease One" if i == Q else "", now=NOW)
    assert "as of 2026-10-03" in card.body_markdown and "didn't find a supported connection yet" in card.body_markdown
    assert card.responsible_human == out.gap.reviewer_role and "indexed evidence" in card.limitations[0]
    assert "Disease One" in card.body_markdown


def test_gap_card_for_science_audience_omits_the_family_copy():
    card = gap_followup(outcome(PublicStore()).gap, audience="science", now=NOW)
    assert "That's an answer too" not in card.body_markdown


def test_asset_card_includes_sourced_status_limits_and_review_needs():
    store = PublicStore()
    a = asset(store, status="active", status_source_url="https://example.invalid/registry", status_checked_at=date(2026, 10, 3))
    card = asset_reuse(a, store.claims, now=NOW)
    body = card.body_markdown
    assert "Status (verbatim from source): active; checked 2026-10-03" in body
    assert "adults only" in body and "confirm the age range" in body and "[^c:CLAIM:asset]" in body
    assert card.asset_ids == ("ASSET:synthetic-1",) and card.responsible_human == "asset owner"


def test_asset_card_refuses_when_its_relevance_claim_is_not_in_the_store():
    with pytest.raises(CardError, match="not in the store"):
        asset_reuse(asset(PublicStore()), {}, now=NOW)


def test_outreach_note_needs_a_verified_public_contact_and_is_a_draft_for_the_user():
    store = PublicStore()
    card = outreach_note(asset(store), store.claims, now=NOW)
    assert card.audience == "family" and "send it yourself" in card.this_week
    assert "https://example.invalid/contact" in card.body_markdown and "Nothing is shared automatically" in card.body_markdown
    with pytest.raises(CardError, match="no verified public contact"):
        outreach_note(asset(PublicStore(), contact=False), store.claims, now=NOW)


def test_clinical_language_in_source_derived_text_is_rejected_by_the_card_validator():
    store = PublicStore()
    bad = asset(store, reuse_limits=("patients should take 5 mg daily",))
    with pytest.raises(ValueError, match="clinical directive"):
        asset_reuse(bad, store.claims, now=NOW)


def test_brief_lists_known_claims_about_the_query_even_when_they_lead_nowhere():
    store = shared_store()
    store.add(make_claim("CLAIM:g", "GENE_ASSOCIATED_WITH_DISEASE", subject_id="HGNC:1", object_id=Q))
    card = evidence_brief(outcome(store), store.claims, now=NOW)
    body = card.body_markdown
    assert "## Known claims about MONDO:0000001" in body and "[^c:CLAIM:g]" in body and "CLAIM:g" in card.claim_ids
