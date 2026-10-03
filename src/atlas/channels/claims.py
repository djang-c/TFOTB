"""T07/T08 claim-overlap channels: compare two diseases through claims already in the PublicStore.

One class, four configurations (docs/implementation/05 sections 2-5). A channel reports overlap
only; it has no numeric score. Missing is never zero: a disease with no claims for the channel
makes the comparison `missing`. Claims sharing a lineage are not independent (see ranking.py).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from atlas.channels.base import EvidenceChannel
from atlas.schemas import ChannelComparison, Claim, ClaimStatus

_DIRECT_NOTE = "directly links the two diseases"


class ClaimOverlapChannel(EvidenceChannel):
    """`predicates`: claims this channel reads. A feature is the end of a claim that is not the
    disease (gene, compartment, study...). Two diseases overlap when they share a feature.

    `supports_category=False` (dna_variants, gene level) keeps matches out of `supporting_claim_ids`
    so a shared gene alone can never make a mechanism lead (docs 05 section 2).
    `observed_only=True` (rna_effects) keeps computational predictions out of the support list.
    """

    version = "1"

    def __init__(
        self,
        store: Any,
        channel_id: str,
        predicates: frozenset[str],
        *,
        supports_category: bool = True,
        observed_only: bool = False,
        note: str = "",
    ) -> None:
        self.store, self.channel_id, self.predicates = store, channel_id, predicates
        self.supports_category, self.observed_only, self.note = supports_category, observed_only, note

    # ---- helpers ----
    def _claims(self) -> list[Claim]:
        return [c for c in self.store.claims.values() if c.predicate in self.predicates]

    @staticmethod
    def _key(claim: Claim, end: str) -> str:
        """A feature is the non-disease end of a claim. An accumulation claim also names WHAT
        accumulates, so 'cholesterol in lysosome' and 'another lipid in lysosome' are different
        features (otherwise every lysosomal storage disease would look connected)."""
        substance = claim.context.get("substance")
        return f"{end}[{substance}]" if substance else end

    def _features(self, entity: str) -> dict[str, list[Claim]]:
        out: dict[str, list[Claim]] = defaultdict(list)
        for c in self._claims():
            if c.subject_id == entity:
                out[self._key(c, c.object_id)].append(c)
            elif c.object_id == entity:
                out[self._key(c, c.subject_id)].append(c)
        return out

    # ---- contract ----
    def retrieve_candidates(self, query_id: str, context: dict[str, Any]) -> list[str]:
        feats = self._features(query_id)
        found: dict[str, None] = {}
        for c in self._claims():
            for disease, other in ((c.subject_id, c.object_id), (c.object_id, c.subject_id)):
                if not disease.startswith("MONDO:") or disease == query_id:
                    continue
                if other == query_id or self._key(c, other) in feats:  # direct link, or a shared feature
                    found.setdefault(disease)
        return sorted(found)

    def compare(self, query_id: str, candidate_id: str, context: dict[str, Any]) -> ChannelComparison:
        base = {
            "channel_id": self.channel_id,
            "channel_version": self.version,
            "query_id": query_id,
            "candidate_id": candidate_id,
        }
        fq, fc = self._features(query_id), self._features(candidate_id)
        direct = [c for c in self._claims() if {c.subject_id, c.object_id} == {query_id, candidate_id}]
        shared = sorted((set(fq) & set(fc)) - {query_id, candidate_id})
        if not direct and not (fq and fc):
            absent = [e for e, f in ((query_id, fq), (candidate_id, fc)) if not f]
            return ChannelComparison(
                **base, availability="missing", missing_fields=[f"claims:{e}" for e in absent],
                limitations=["no claims for this channel in the store; missing is not zero"],
            )

        support: list[Claim] = list(direct)
        matches = [f"{_DIRECT_NOTE}: {c.predicate} ({c.claim_id})" for c in direct]
        mismatches: set[str] = set()
        limits = [self.note] if self.note else []
        for feat in shared:
            claims_q, claims_c = fq[feat], fc[feat]
            both = claims_q + claims_c
            if not self.supports_category:
                limits.append(f"same {feat} reported on both sides, not variant-level evidence: " + ", ".join(sorted(c.claim_id for c in both)))
                matches.append(f"shared {feat}")
                continue
            kept = [c for c in both if not (self.observed_only and c.status is ClaimStatus.computational_prediction)]
            for c in both:
                if c not in kept:
                    limits.append(f"predicted, not observed, excluded from support: {c.claim_id}")
            support += kept
            matches.append(f"shared {feat}")
            dirs_q = {c.context["direction"] for c in claims_q if c.context.get("direction")}
            dirs_c = {c.context["direction"] for c in claims_c if c.context.get("direction")}
            if dirs_q and dirs_c and dirs_q.isdisjoint(dirs_c):
                mismatches.add("effect_direction")
            tissues_q = {c.context.get("tissue") for c in claims_q if c.context.get("tissue")}
            tissues_c = {c.context.get("tissue") for c in claims_c if c.context.get("tissue")}
            if tissues_q and tissues_c and not tissues_q & tissues_c:
                mismatches.add("tissue")
            assays_q = {c.context.get("assay") for c in claims_q if c.context.get("assay")}
            assays_c = {c.context.get("assay") for c in claims_c if c.context.get("assay")}
            if assays_q and assays_c and not assays_q & assays_c:
                mismatches.add("assay")  # unlike assays: flagged, never pooled (no number is produced here)
        if not self.supports_category:
            support = []
        if not matches:
            limits.append("both diseases have claims here but share no feature")
        seen: set[str] = set()
        ids = [c.claim_id for c in support if not (c.claim_id in seen or seen.add(c.claim_id))]
        return ChannelComparison(
            **base,
            availability="available",
            supporting_claim_ids=ids,
            context_matches=matches,
            context_mismatches=sorted(mismatches),
            limitations=limits,
        )


def build_claim_channels(store: Any) -> list[ClaimOverlapChannel]:
    """The four claim-backed channels with the predicate sets from docs 05."""
    return [
        ClaimOverlapChannel(
            store, "dna_variants", frozenset({"GENE_ASSOCIATED_WITH_DISEASE"}), supports_category=False,
            note="gene-level only: no variant-level claims are modelled yet",
        ),
        ClaimOverlapChannel(
            store, "rna_effects", frozenset({"HAS_OBSERVED_RNA_EFFECT", "HAS_PREDICTED_RNA_EFFECT"}), observed_only=True,
        ),
        ClaimOverlapChannel(
            store, "molecular_mechanisms",
            frozenset({"PERTURBS_MECHANISM", "ACCUMULATES_IN_COMPARTMENT", "SHARES_PATHOGENIC_PATHWAY_WITH"}),
        ),
        ClaimOverlapChannel(store, "experimental_findings", frozenset({"INVESTIGATED_IN", "SUPPORTED_BY"})),
    ]
