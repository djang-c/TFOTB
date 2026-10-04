"""Public evidence store + isolated synthetic case store (PLAN: T11, T15 foundations)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from atlas.extraction import ExtractionReport
from atlas.privacy import contains_private_marker
from atlas.schemas import Claim, ClaimStatus, ReviewState, SourceType


class PublicStore:
    def __init__(self) -> None:
        self.claims: dict[str, Claim] = {}
        self.quarantine: list[dict[str, Any]] = []
        # One record per ingested extraction; coverage counts come from these, not from generated text.
        self.extraction_runs: list[dict[str, Any]] = []

    def add(self, claim: Claim) -> None:
        self.claims[claim.claim_id] = claim

    def ingest_extraction(self, report: ExtractionReport) -> dict[str, Any]:
        """Store the verified claims from one T04 extraction; keep every rejection with its reason.

        Re-ingesting an identical claim is a no-op; a claim_id that exists with different content is
        quarantined, never overwritten.
        """
        added = already = 0
        for claim in report.claims:
            existing = self.claims.get(claim.claim_id)
            if existing is None:
                self.add(claim)
                added += 1
            elif existing == claim:
                already += 1
            else:
                self.quarantine.append(
                    {
                        "source_id": report.source_id,
                        "claim_id": claim.claim_id,
                        "error": "claim_id exists with different content; not overwritten",
                    }
                )
        for rejected in report.quarantined:
            self.quarantine.append(
                {"source_id": report.source_id, "payload": rejected["statement"], "error": rejected["reason"]}
            )
        run = {
            "source_id": report.source_id,
            "status": report.status,
            "reason": report.reason,
            "provider": report.provider,
            "model": report.model,
            "prompt_version": report.prompt_version,
            "from_cache": report.from_cache,
            "claims_added": added,
            "claims_already_present": already,
            "statements_quarantined": len(report.quarantined),
        }
        self.extraction_runs.append(run)
        return run

    def ingest_lab_finding(self, payload: dict[str, Any]) -> Claim | None:
        """Uploads are always lab_reported + unreviewed; payload text is data, not instructions."""
        forced = {
            **payload,
            "source_type": SourceType.lab_reported,
            "review_state": ReviewState.unreviewed,
            "status": ClaimStatus.reported_observation,
        }
        try:
            if not forced.get("contributor"):
                raise ValueError("contributor attribution required")
            if contains_private_marker(json.dumps(forced, ensure_ascii=False, default=str)):
                raise ValueError("private or synthetic case data cannot enter the public store")
            claim = Claim(**forced)
            if claim.claim_id in self.claims:
                raise ValueError(f"claim_id {claim.claim_id} already exists; uploads cannot overwrite")
        except (ValidationError, ValueError, TypeError) as exc:
            self.quarantine.append({"payload": payload, "error": str(exc)[:300]})
            return None
        self.add(claim)
        return claim

    def search(self, term: str) -> list[Claim]:
        t = term.strip().lower()
        if not t:
            return []  # an empty term must not match every claim
        return [
            c
            for c in self.claims.values()
            if t in c.subject_id.lower() or t in c.object_id.lower() or t in c.source_span.lower()
        ]


@dataclass
class SyntheticCase:
    case_id: str
    phenotype_ids: list[str]
    variant_ids: list[str]
    label: str = "SYNTHETIC - software test fixture only"


@dataclass
class CaseStore:
    """Never writes into PublicStore. Derived associations stay here."""

    cases: dict[str, SyntheticCase] = field(default_factory=dict)
    derived: dict[str, list[str]] = field(default_factory=dict)

    def add(self, case: SyntheticCase) -> None:
        if not case.case_id.startswith("CASE-SYN-"):
            raise ValueError("only synthetic cases are accepted in the MVP")
        self.cases[case.case_id] = case

    def match_to_public(self, case_id: str, public: PublicStore) -> list[str]:
        case = self.cases[case_id]
        hits = sorted(
            {
                c.claim_id
                for term in (*case.phenotype_ids, *case.variant_ids)
                for c in public.search(term)
            }
        )
        self.derived[case_id] = hits
        return hits
