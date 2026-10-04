"""Evidence qualification gates (PLAN: T09). No combined probability, no default weights."""

from __future__ import annotations

from atlas.schemas import (
    HYPOTHESIS_ONLY_PREDICATES,
    Availability,
    ChannelComparison,
    Claim,
    ClaimStatus,
    ConnectionResult,
    EvidenceCategory,
    ReviewState,
    SourceType,
)

MECHANISM_CHANNELS = frozenset(
    {"dna_variants", "rna_effects", "molecular_mechanisms", "experimental_findings"}
)
BLOCKING_MISMATCHES = frozenset({"effect_direction"})
CREDIBLE_SOURCES = frozenset({SourceType.published, SourceType.database_record})


def _is_background(c: Claim) -> bool:
    return c.context.get("scope") == "background"


def independent_support_count(claim_ids: list[str], claims: dict[str, Claim]) -> int:
    """Independent studies: lineages with at least one claim that is the study's own finding. Claims
    sharing a lineage (same experiment) count once. A paper that only cites a statement as already
    known is not an independent study of it; see `background_support_count`."""
    return len({claims[c].lineage_id for c in claim_ids if c in claims and not _is_background(claims[c])})


def background_support_count(claim_ids: list[str], claims: dict[str, Claim]) -> int:
    """Papers that restate the claim as background knowledge and do not report it as their own finding.
    This adds some weight (the statement is widely accepted) but far less than an independent study,
    and it is shown as its own number, never merged into the independent count."""
    own = {claims[c].lineage_id for c in claim_ids if c in claims and not _is_background(claims[c])}
    cited = {claims[c].lineage_id for c in claim_ids if c in claims and _is_background(claims[c])}
    return len(cited - own)


def shared_treatment_inference_allowed(comps: list[ChannelComparison]) -> bool:
    """Opposing mechanism direction blocks an unsupported shared-treatment inference."""
    return not any(m in BLOCKING_MISMATCHES for c in comps for m in c.context_mismatches)


def categorize(comps: list[ChannelComparison], claims: dict[str, Claim]) -> EvidenceCategory:
    avail = [c for c in comps if c.availability is Availability.available]
    if not avail:
        return EvidenceCategory.insufficient_coverage
    if any(c.contradicting_claim_ids for c in avail):
        return EvidenceCategory.conflicting_evidence
    # A mechanism channel counts only when it supports something: two diseases that both have gene
    # claims but share no gene are not mechanism evidence, and must not demote a symptom-level lead.
    mech = [c for c in avail if c.channel_id in MECHANISM_CHANNELS and (c.supporting_claim_ids or c.contradicting_claim_ids)]
    if not mech:
        if any(c.channel_id == "phenotype" for c in avail):
            return EvidenceCategory.symptom_level_lead
        return EvidenceCategory.hypothesis_only
    literature = False
    for c in mech:
        # simulation artifacts are engineering records, never biological support
        sup = [
            claims[i]
            for i in c.supporting_claim_ids
            if i in claims
            and claims[i].predicate != "SIMULATES_WORKFLOW_FOR"
            and claims[i].predicate not in HYPOTHESIS_ONLY_PREDICATES
        ]
        if sup and all(
            s.review_state is ReviewState.reviewed and s.status is ClaimStatus.reported_observation
            for s in sup
        ):
            return EvidenceCategory.reviewed_mechanistic_lead
        # Observed in published or database sources but not expert-reviewed: shown with its own label
        # (owner decision 2026-10-04: review is a label, not a gate). Uploads and fixtures never qualify.
        if sup and all(s.status is ClaimStatus.reported_observation and s.source_type in CREDIBLE_SOURCES for s in sup):
            literature = True
    return EvidenceCategory.literature_supported_lead if literature else EvidenceCategory.hypothesis_only


def build_result(
    query_id: str,
    candidate_id: str,
    comps: list[ChannelComparison],
    claims: dict[str, Claim],
    coverage_manifest_id: str | None = None,
) -> ConnectionResult:
    flags = sorted({f"{c.channel_id}:{m}" for c in comps for m in c.context_mismatches})
    path = sorted({i for c in comps for i in c.supporting_claim_ids})
    return ConnectionResult(
        query_id=query_id,
        candidate_id=candidate_id,
        comparisons=comps,
        category=categorize(comps, claims),
        compatibility_flags=flags,
        path_claim_ids=path,
        coverage_manifest_id=coverage_manifest_id,
        shared_treatment_inference_allowed=shared_treatment_inference_allowed(comps),
    )
