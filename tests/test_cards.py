"""T10 card tests. Claims, assets and contacts are SYNTHETIC test fixtures."""

from datetime import UTC, date, datetime

import pytest
from tests.conftest import make_claim

from atlas.cards import (
    CardError,
    asset_reuse,
    evidence_brief,
    gap_followup,
    outreach_note,
    simulation_report,
)
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


def test_brief_with_nothing_cited_never_mentions_reviewed_claims():
    # Found on real data: phenotype-only candidates cite no claim, and the step used to say
    # "confirm the reviewed claims", implying reviewed evidence that does not exist.
    card = evidence_brief(outcome(PublicStore()), {}, now=NOW)
    assert "reviewed claims" not in card.this_week and "no claim is cited" in card.this_week


def test_brief_shows_readable_routes_with_footnotes_and_labels_hypothesis_only_ones():
    store = shared_store()
    store.add(make_claim("CLAIM:h", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=Q, object_id=A, status="inference"))
    card = evidence_brief(outcome(store), store.claims, label_of=lambda i: {"GO:0005764": "lysosome"}.get(i, ""), now=NOW)
    routes = [x for x in card.body_markdown.splitlines() if "→" in x]
    assert any("lysosome" in x and "hypothesis only" not in x and "[^c:CLAIM:q]" in x for x in routes)
    assert any("**hypothesis only**" in x and "[^c:CLAIM:h]" in x for x in routes)


def test_brief_says_when_no_route_exists_without_claiming_absence():
    from atlas.channels.base import EvidenceChannel
    from atlas.schemas import ChannelComparison

    class Phen(EvidenceChannel):
        channel_id, version = "phenotype", "1"

        def retrieve_candidates(self, query_id, context):
            return [A]

        def compare(self, query_id, candidate_id, context):
            return ChannelComparison(
                channel_id="phenotype", channel_version="1", query_id=query_id, candidate_id=candidate_id,
                availability="available", score=0.4, score_definition="test similarity",
            )

    reg = ChannelRegistry()
    reg.register(Phen())
    out = run_query(Q, reg, {}, dataset_version="t", per_source=[], now=NOW)
    body = evidence_brief(out, {}, now=NOW).body_markdown
    assert "none of up to 4 steps" in body and "not proof of absence" in body


def _sim(**kw):
    base = {
        "run_id": "run-abc", "experiment_spec_hash": "a" * 64, "scene_hash": "b" * 64, "simulator_name": "mujoco",
        "simulator_version": "3.14.0", "random_seed": 0, "review_state": "generic_fixture_unreviewed",
        "overall": "pass", "scope_label": "Workflow simulation only; not wet-lab validated", "failures": [],
        "checks": [
            {"check_name": "joint_limits", "status": "pass", "reason": ""},
            {"check_name": "biology", "status": "not_modeled", "reason": "not simulated"},
            {"check_name": "physical_execution", "status": "not_modeled", "reason": "no hardware"},
        ],
    }
    return {**base, **kw}


def test_simulation_card_states_scope_hashes_and_that_biology_is_not_modelled():
    card = simulation_report(_sim(), {}, now=NOW)
    b = card.body_markdown
    assert card.kind == "simulation_report" and "not wet-lab validated" in b and "a" * 64 in b
    assert "does not show that any biological idea is right" in b and "not_modeled" in b
    assert card.responsible_human == "lab-automation engineer (unassigned)" and card.claim_ids == ()


def test_simulation_card_reports_failures_verbatim_and_asks_for_a_fix():
    fail = [{"op_index": 2, "check": "modeled_collision", "reason": "unexpected contact ['a', 'b']"}]
    card = simulation_report(_sim(overall="fail", failures=fail), {}, now=NOW)
    assert "FAIL" in card.body_markdown and "unexpected contact ['a', 'b']" in card.body_markdown
    assert "fix or reject" in card.this_week


def test_simulation_card_refuses_a_report_that_does_not_mark_biology_not_modelled():
    bad = _sim(checks=[{"check_name": "biology", "status": "pass", "reason": ""}])
    with pytest.raises(CardError, match="not_modeled"):
        simulation_report(bad, {}, now=NOW)
    with pytest.raises(CardError, match="missing"):
        simulation_report({"run_id": "x"}, {}, now=NOW)


def test_simulation_card_cites_source_claims_only_if_they_are_stored():
    store = shared_store()
    card = simulation_report(_sim(), store.claims, source_claim_ids=("CLAIM:q",), now=NOW)
    assert "[^c:CLAIM:q]" in card.body_markdown and card.claim_ids == ("CLAIM:q",)
    with pytest.raises(CardError, match="not in the store"):
        simulation_report(_sim(), store.claims, source_claim_ids=("CLAIM:nope",), now=NOW)


def test_brief_labels_ai_found_claims_with_their_article_and_ai_hypotheses_with_their_basis():
    store = shared_store()
    paper = make_claim(
        "CLAIM:p", "ACCUMULATES_IN_COMPARTMENT", subject_id=Q, object_id="GO:0005770", source_type="published",
        source_url="https://doi.org/10.1000/real", extraction_method="llm:m@extract-v4",
    )
    hyp = make_claim(
        "CLAIM:HYP-1", "SHARES_PATHOGENIC_PATHWAY_WITH", subject_id=Q, object_id=A, status="inference",
        source_type="ai_generated", source_url="atlas:ai-hypothesis", derived_from=("CLAIM:q", "CLAIM:a"),
    )
    store.add(paper)
    store.add(hyp)
    card = evidence_brief(outcome(store), store.claims, now=NOW)
    lines = {x.split("[^c:")[-1].split("]")[0]: x for x in card.body_markdown.splitlines() if x.startswith("- ") and "[^c:" in x}
    assert "found by AI in https://doi.org/10.1000/real" in lines["CLAIM:p"]
    h = lines["CLAIM:HYP-1"]
    assert "AI hypothesis, not a finding" in h and "built from [^c:CLAIM:q] [^c:CLAIM:a]" in h and "**hypothesis only**" in h
    assert {"CLAIM:q", "CLAIM:a"} <= set(card.claim_ids)
