"""Evidence qualification gates (PLAN: T09). No combined probability, no default weights."""

from __future__ import annotations

from atlas.schemas import (
    Availability,
    ChannelComparison,
    Claim,
    ClaimStatus,
    ConnectionResult,
    EvidenceCategory,
    ReviewState,
)

MECHANISM_CHANNELS = frozenset(
    {"dna_variants", "rna_effects", "molecular_mechanisms", "experimental_findings"}
)
BLOCKING_MISMATCHES = frozenset({"effect_direction"})


def independent_support_count(claim_ids: list[str], claims: dict[str, Claim]) -> int:
    """Claims sharing a lineage (same experiment) count once."""
    return len({claims[c].lineage_id for c in claim_ids if c in claims})


def shared_treatment_inference_allowed(comps: list[ChannelComparison]) -> bool:
    """Opposing mechanism direction blocks an unsupported shared-treatment inference."""
    return not any(m in BLOCKING_MISMATCHES for c in comps for m in c.context_mismatches)


def categorize(comps: list[ChannelComparison], claims: dict[str, Claim]) -> EvidenceCategory:
    avail = [c for c in comps if c.availability is Availability.available]
    if not avail:
        return EvidenceCategory.insufficient_coverage
    if any(c.contradicting_claim_ids for c in avail):
        return EvidenceCategory.conflicting_evidence
    mech = [c for c in avail if c.channel_id in MECHANISM_CHANNELS]
    if not mech:
        if any(c.channel_id == "phenotype" for c in avail):
            return EvidenceCategory.symptom_level_lead
        return EvidenceCategory.hypothesis_only
    for c in mech:
        # simulation artifacts are engineering records, never biological support
        sup = [
            claims[i]
            for i in c.supporting_claim_ids
            if i in claims and claims[i].predicate != "SIMULATES_WORKFLOW_FOR"
        ]
        if sup and all(
            s.review_state is ReviewState.reviewed and s.status is ClaimStatus.reported_observation
            for s in sup
        ):
            return EvidenceCategory.reviewed_mechanistic_lead
    return EvidenceCategory.hypothesis_only


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
