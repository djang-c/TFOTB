"""Versioned data contracts (PLAN: T02). Pure validation; no I/O."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "0.1.0"

# Only real, namespace-correct identifiers pass. "HGNC:GBA1" (symbol appended to a prefix) fails.
_CURIE = {
    "MONDO": r"\d{7}",
    "HP": r"\d{7}",
    "HGNC": r"\d{1,6}",
    "CHEBI": r"\d+",
    "REACT": r"R-[A-Z]{3}-\d+",
    "GO": r"\d{7}",
    "NCT": r"\d{8}",
    "FINDING": r"[A-Za-z0-9_.-]+",
    "CLAIM": r"[A-Za-z0-9_.-]+",
    "ASSET": r"[A-Za-z0-9_.-]+",
    "STUDY": r"[A-Za-z0-9_.-]+",
    "VARIANT": r"[A-Za-z0-9_.:>-]+",
    "TRANSCRIPT": r"[A-Za-z0-9_.]+",
}


def validate_curie(value: str) -> str:
    prefix, sep, local = value.partition(":")
    pattern = _CURIE.get(prefix)
    if not sep or pattern is None or not re.fullmatch(pattern, local):
        raise ValueError(f"unresolved or malformed identifier: {value!r}")
    return value


ALLOWED_PREDICATES = frozenset(
    {
        "AFFECTS_TRANSCRIPT",
        "ASSOCIATED_WITH_PHENOTYPE",
        "HAS_OBSERVED_RNA_EFFECT",
        "HAS_PREDICTED_RNA_EFFECT",
        "PERTURBS_MECHANISM",
        "SUPPORTED_BY",
        "CONTRADICTED_BY",
        "INVESTIGATED_IN",
        "ASSET_RELEVANT_TO",
        "SIMULATES_WORKFLOW_FOR",
    }
)
STRONG_CAUSAL = frozenset({"AFFECTS_TRANSCRIPT", "PERTURBS_MECHANISM"})


class ClaimStatus(str, Enum):
    reported_observation = "reported_observation"
    computational_prediction = "computational_prediction"
    inference = "inference"


class ReviewState(str, Enum):
    unreviewed = "unreviewed"
    reviewed = "reviewed"
    disputed = "disputed"


class SourceType(str, Enum):
    published = "published"
    database_record = "database_record"
    lab_reported = "lab_reported"
    synthetic_fixture = "synthetic_fixture"


class Availability(str, Enum):
    available = "available"
    missing = "missing"
    incompatible = "incompatible"
    failed = "failed"


class EvidenceCategory(str, Enum):
    reviewed_mechanistic_lead = "reviewed mechanistic lead"
    symptom_level_lead = "symptom-level lead"
    hypothesis_only = "hypothesis only"
    conflicting_evidence = "conflicting evidence"
    insufficient_coverage = "insufficient coverage"


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    schema_version: str = SCHEMA_VERSION
    subject_id: str
    predicate: str
    object_id: str
    source_url: str
    source_span: str = Field(min_length=1, description="quoted text or structured source field")
    source_type: SourceType
    status: ClaimStatus
    review_state: ReviewState = ReviewState.unreviewed
    lineage_id: str = Field(
        description="originating experiment/study; shared lineage = not independent"
    )
    context: dict[str, Any] = Field(default_factory=dict)  # organism, tissue, direction, assay...
    contradicts: tuple[str, ...] = ()
    score: float | None = None
    score_definition: str | None = None
    contributor: str | None = None

    @field_validator("subject_id", "object_id")
    @classmethod
    def _ids(cls, v: str) -> str:
        return validate_curie(v)

    @field_validator("predicate")
    @classmethod
    def _predicate(cls, v: str) -> str:
        if v not in ALLOWED_PREDICATES:
            raise ValueError(f"predicate not allowed: {v}")
        return v

    @model_validator(mode="after")
    def _rules(self) -> Claim:
        if self.predicate in STRONG_CAUSAL and self.status is ClaimStatus.inference:
            raise ValueError("strong causal predicate cannot rest on an inference")
        if self.score is not None and not self.score_definition:
            raise ValueError("a score requires a documented score_definition")
        return self


class ChannelComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_version: str
    query_id: str
    candidate_id: str
    availability: Availability
    score: float | None = None
    score_definition: str | None = None
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    context_matches: list[str] = Field(default_factory=list)
    context_mismatches: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _missingness(self) -> ChannelComparison:
        if self.availability is not Availability.available and self.score is not None:
            raise ValueError("missing/incompatible/failed channels must carry score=None")
        if self.score is not None and not self.score_definition:
            raise ValueError("score requires an explicit score_definition (not 'confidence')")
        return self


class ConnectionResult(BaseModel):
    query_id: str
    candidate_id: str
    comparisons: list[ChannelComparison]
    category: EvidenceCategory
    compatibility_flags: list[str] = Field(default_factory=list)
    path_claim_ids: list[str] = Field(default_factory=list)
    coverage_manifest_id: str | None = None
    shared_treatment_inference_allowed: bool = False
    scope_note: str = "Research-support lead. Not a diagnosis or treatment recommendation."
