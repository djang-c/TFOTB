"""T09: run a query through the channel registry, apply the evidence gates, rank, and report coverage.

Rules (PLAN, docs/implementation/05 section 6):
- Results are grouped by evidence category; the category comes from `ranking.categorize`.
- Within a category the order uses only tie-breakers (direct link > indirect, reviewed support >
  unreviewed, fewer context mismatches, more independent lineages, then ID). No score, numeric or
  otherwise, orders results; a channel's own number is displayed but never ranks.
- The coverage manifest is built from recorded operations passed in by the caller; nothing here
  invents a count. A query with nothing above "hypothesis only" yields a scoped GapResult.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from atlas.channels.base import ChannelRegistry
from atlas.ranking import build_result, independent_support_count
from atlas.schemas import (
    Availability,
    ChannelCoverage,
    Claim,
    ConnectionResult,
    CoverageManifest,
    EvidenceCategory,
    GapResult,
    ReviewState,
    SourceCoverage,
    SourceStatus,
)

CATEGORY_ORDER = list(EvidenceCategory)
GENERATED_BY = "atlas.connections v1"
REVIEWER_ROLE = "domain expert (unassigned; claims are unreviewed)"


@dataclass(frozen=True)
class RankedConnection:
    result: ConnectionResult
    direct: bool
    reviewed_support: int
    independent_lineages: int


@dataclass(frozen=True)
class QueryOutcome:
    query_id: str
    ranked: list[RankedConnection]
    coverage: CoverageManifest
    gap: GapResult | None


def sources_from_extraction_runs(runs: list[dict[str, Any]]) -> list[SourceCoverage]:
    """Recorded T04 runs -> per-source coverage. fetched = statements the model proposed,
    screened = statements that passed every check (a claim stored or already present)."""
    out = []
    for r in runs:
        if r["status"] != "extracted":
            out.append(SourceCoverage(source=r["source_id"], status=SourceStatus.failed, error=r["reason"] or "not extracted"))
            continue
        passed = r["claims_added"] + r["claims_already_present"]
        out.append(
            SourceCoverage(
                source=r["source_id"], version=r["prompt_version"], status=SourceStatus.ok,
                fetched=passed + r["statements_quarantined"], screened=passed,
            )
        )
    return out


def _is_direct(result: ConnectionResult, claims: dict[str, Claim]) -> bool:
    pair = {result.query_id, result.candidate_id}
    return any(
        {claims[i].subject_id, claims[i].object_id} == pair for i in result.path_claim_ids if i in claims
    )


def _rank_key(r: RankedConnection) -> tuple:
    return (
        CATEGORY_ORDER.index(r.result.category),
        not r.direct,
        -r.reviewed_support,
        len(r.result.compatibility_flags),
        -r.independent_lineages,
        r.result.candidate_id,
    )


def _channel_coverage(per_pair: list[list[Any]]) -> tuple[ChannelCoverage, ...]:
    by_channel: dict[str, list[Availability]] = {}
    for comps in per_pair:
        for c in comps:
            by_channel.setdefault(c.channel_id, []).append(c.availability)
    out = []
    for cid, avs in sorted(by_channel.items()):
        n_ok = sum(a is Availability.available for a in avs)
        best = Availability.available if n_ok else (Availability.failed if Availability.failed in avs else avs[0])
        out.append(ChannelCoverage(channel_id=cid, availability=best, note=f"available for {n_ok} of {len(avs)} candidates"))
    return tuple(out)


def _manifest_id(query_id: str, dataset_version: str, claim_ids: list[str]) -> str:
    blob = "|".join([query_id, dataset_version, *sorted(claim_ids)])
    return f"COV:{query_id.replace(':', '-')}-{hashlib.sha256(blob.encode()).hexdigest()[:10]}"


def run_query(
    query_id: str,
    registry: ChannelRegistry,
    claims: dict[str, Claim],
    *,
    dataset_version: str,
    per_source: list[SourceCoverage],
    source_versions: dict[str, str] | None = None,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> QueryOutcome:
    ctx = context or {}
    now = now or datetime.now(UTC)
    candidates = registry.candidate_union(query_id, ctx)
    comps_by_cand = {c: registry.compare_all(query_id, c, ctx) for c in candidates}
    manifest = CoverageManifest(
        manifest_id=_manifest_id(query_id, dataset_version, list(claims)),
        query=query_id,
        dataset_version=dataset_version,
        source_versions=source_versions or {},
        retrieved_at=now,
        filters={"candidates_considered": len(candidates), **{k: v for k, v in ctx.items() if k != "now"}},
        per_source=tuple(per_source),
        per_channel=_channel_coverage(list(comps_by_cand.values())),
        generated_by=GENERATED_BY,
    )
    ranked = []
    for cand, comps in comps_by_cand.items():
        res = build_result(query_id, cand, comps, claims, coverage_manifest_id=manifest.manifest_id)
        reviewed = sum(1 for i in res.path_claim_ids if i in claims and claims[i].review_state is ReviewState.reviewed)
        ranked.append(
            RankedConnection(res, _is_direct(res, claims), reviewed, independent_support_count(res.path_claim_ids, claims))
        )
    ranked.sort(key=_rank_key)
    return QueryOutcome(query_id, ranked, manifest, _gap(query_id, ranked, manifest, now))


def _gap(query_id: str, ranked: list[RankedConnection], manifest: CoverageManifest, now: datetime) -> GapResult | None:
    cats = {r.result.category for r in ranked}
    if cats & {EvidenceCategory.reviewed_mechanistic_lead, EvidenceCategory.symptom_level_lead}:
        return None
    day = now.date()
    if not ranked:
        kind = "no_supported_route"
        why = "no candidate connection was retrieved by any channel"
    elif EvidenceCategory.conflicting_evidence in cats:
        kind, why = "conflicting_evidence", "the available evidence conflicts"
    elif EvidenceCategory.hypothesis_only in cats:
        kind, why = "hypothesis_only", "all connections rest on unreviewed or hypothesis-level evidence"
    else:
        kind, why = "insufficient_coverage", "every channel lacked data for the candidates compared"
    missing = sorted({m for r in ranked for c in r.result.comparisons for m in c.missing_fields})
    known = sorted({i for r in ranked for i in r.result.path_claim_ids})
    return GapResult(
        kind=kind,
        statement=f"No supported route found in the indexed evidence as of {day.isoformat()}: {why}.",
        as_of=day,
        entity_id=query_id,
        coverage_manifest_id=manifest.manifest_id,
        known_claim_ids=tuple(known),
        failed_sources=tuple(s.source for s in manifest.per_source if s.status is SourceStatus.failed),
        missing_information=tuple(missing[:20]) or ("expert review of the unreviewed claims",),
        reviewer_role=REVIEWER_ROLE,
    )
