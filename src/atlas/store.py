"""Public evidence store + isolated synthetic case store (PLAN: T11, T15 foundations)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from atlas.schemas import Claim, ClaimStatus, ReviewState, SourceType


class PublicStore:
    def __init__(self) -> None:
        self.claims: dict[str, Claim] = {}
        self.quarantine: list[dict[str, Any]] = []

    def add(self, claim: Claim) -> None:
        self.claims[claim.claim_id] = claim

    def ingest_lab_finding(self, payload: dict[str, Any]) -> Claim | None:
        """Uploads are always lab_reported + unreviewed. Payload text is data, never instructions."""
        forced = {
            **payload,
            "source_type": SourceType.lab_reported,
            "review_state": ReviewState.unreviewed,
            "status": ClaimStatus.reported_observation,
        }
        try:
            if not forced.get("contributor"):
                raise ValueError("contributor attribution required")
            claim = Claim(**forced)
        except (ValidationError, ValueError, TypeError) as exc:
            self.quarantine.append({"payload": payload, "error": str(exc)[:300]})
            return None
        self.add(claim)
        return claim

    def search(self, term: str) -> list[Claim]:
        t = term.lower()
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
