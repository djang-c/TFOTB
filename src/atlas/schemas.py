"""Versioned data contracts (PLAN: T02). Pure validation; no I/O."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "0.2.0"

# Only real, namespace-correct identifiers pass. "HGNC:GBA1" (symbol appended to a prefix) fails.
# External prefixes use Bioregistry's preferred spelling (https://bioregistry.io).
_SLUG = r"[A-Za-z0-9_.-]+"
_CURIE = {
    "MONDO": r"\d{7}",
    "HP": r"\d{7}",
    "HGNC": r"\d{1,6}",
    "NCBIGene": r"\d+",
    "ENSEMBL": r"ENS[A-Z]*[GTP]\d{11}(\.\d+)?",
    "UniProtKB": r"([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})(-\d+)?",
    "ORPHA": r"\d+",
    "OMIM": r"\d{6}",  # xref only (licence)
    "CHEBI": r"\d+",
    "REACT": r"R-[A-Z]{3}-\d+",
    "GO": r"\d{7}",
    "NCT": r"\d{8}",
    "PMID": r"\d+",
    "ORCID": r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]",
    "infores": r"[a-z0-9_.-]+",
    # Scoped internal IDs (never built from an external label; see T03).
    "ORG": _SLUG,
    "INV": _SLUG,
    "COV": _SLUG,
    "CARD": _SLUG,
    "RUN": _SLUG,
    "SIM": _SLUG,
    "UNRESOLVED": _SLUG,
    # SYNTHETIC demo/test records only; never a real ontology ID (see Entity._identity).
    "SYN": _SLUG,
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


CurieStr = Annotated[str, AfterValidator(validate_curie)]


def _current_version(v: str) -> str:
    if v != SCHEMA_VERSION:
        raise ValueError(f"schema_version {v!r} != {SCHEMA_VERSION}; migrate or rebuild the record")
    return v


SchemaVersion = Annotated[str, AfterValidator(_current_version)]


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
        # Added 2026-10-03 (docs/DECISIONS.md): disease-level and breadth-layer relationships.
        "GENE_ASSOCIATED_WITH_DISEASE",  # gene -> disease, association only (not causal)
        "ACCUMULATES_IN_COMPARTMENT",  # disease -> GO cellular component, observed in a study
        "SHARES_PATHOGENIC_PATHWAY_WITH",  # disease -> disease, hypothesis-only
        "CANDIDATE_THERAPY_FOR",  # CHEBI compound -> disease, hypothesis-only, never a recommendation
    }
)
STRONG_CAUSAL = frozenset({"AFFECTS_TRANSCRIPT", "PERTURBS_MECHANISM"})
# Statements that are inferences or hopes even when a paper says them: they can never be recorded
# as an observation and never support a "reviewed mechanistic lead".
HYPOTHESIS_ONLY_PREDICATES = frozenset({"SHARES_PATHOGENIC_PATHWAY_WITH", "CANDIDATE_THERAPY_FOR"})


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
    ai_generated = "ai_generated"  # a model-made hypothesis; never counts as literature support


class Availability(str, Enum):
    available = "available"
    missing = "missing"
    incompatible = "incompatible"
    failed = "failed"


class EvidenceCategory(str, Enum):
    reviewed_mechanistic_lead = "reviewed mechanistic lead"
    literature_supported_lead = "literature-supported lead"  # observed in published sources; NOT expert-reviewed
    symptom_level_lead = "symptom-level lead"
    hypothesis_only = "hypothesis only"
    conflicting_evidence = "conflicting evidence"
    insufficient_coverage = "insufficient coverage"


class KnowledgeLevel(str, Enum):
    """Biolink KnowledgeLevelEnum (https://biolink.github.io/biolink-model/KnowledgeLevelEnum/)."""

    knowledge_assertion = "knowledge_assertion"
    logical_entailment = "logical_entailment"
    prediction = "prediction"
    statistical_association = "statistical_association"
    observation = "observation"
    text_co_occurrence = "text_co_occurrence"
    not_provided = "not_provided"


class AgentType(str, Enum):
    """Biolink AgentTypeEnum (https://biolink.github.io/biolink-model/AgentTypeEnum/)."""

    manual_agent = "manual_agent"
    automated_agent = "automated_agent"
    data_analysis_pipeline = "data_analysis_pipeline"
    computational_model = "computational_model"
    text_mining_agent = "text_mining_agent"
    image_processing_agent = "image_processing_agent"
    manual_validation_of_automated_agent = "manual_validation_of_automated_agent"
    not_provided = "not_provided"


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    schema_version: SchemaVersion = SCHEMA_VERSION
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
    contradicts: tuple[CurieStr, ...] = ()
    score: float | None = None
    score_definition: str | None = None
    contributor: str | None = None
    # PLAN "Every claim must record" (0.2.0). Optional so unknown stays None, never a guessed value.
    published_at: date | None = None
    retrieved_at: date | None = None
    extraction_method: str | None = None  # e.g. "structured_field", "llm:<model>@<prompt_version>"
    source_reported_classification: str | None = None  # verbatim, e.g. a ClinVar significance
    review_notes: tuple[str, ...] = ()
    derived_from: tuple[CurieStr, ...] = ()  # claim IDs this claim restates or was derived from
    knowledge_level: KnowledgeLevel = KnowledgeLevel.not_provided
    agent_type: AgentType = AgentType.not_provided
    primary_knowledge_source: str | None = None  # infores CURIE

    @field_validator("subject_id", "object_id")
    @classmethod
    def _ids(cls, v: str) -> str:
        return validate_curie(v)

    @field_validator("source_url")
    @classmethod
    def _safe_source_url(cls, v: str) -> str:
        # A source is a web page or an internal pointer. `javascript:` / `data:` addresses must never be stored,
        # because a source link is rendered to readers.
        if not v.startswith(("https://", "http://", "atlas:", "local:")):
            raise ValueError("source_url must start with https://, http://, atlas: or local:")
        return v

    @field_validator("primary_knowledge_source")
    @classmethod
    def _infores(cls, v: str | None) -> str | None:
        return v if v is None else _prefixed(v, "infores")

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
        if self.predicate in HYPOTHESIS_ONLY_PREDICATES and self.status is ClaimStatus.reported_observation:
            raise ValueError(f"{self.predicate} is hypothesis-only; status must be inference or computational_prediction")
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


# --- T02: entities, coverage, gaps, assets, action cards (docs/implementation/03 §2) ---

_STRICT = ConfigDict(frozen=True, extra="forbid")


def _prefixed(value: str, prefix: str) -> str:
    if not value.startswith(f"{prefix}:"):
        raise ValueError(f"expected a {prefix}: id, got {value!r}")
    return validate_curie(value)

_EMAIL = re.compile(r"[^\s@/]+@[^\s@/]+\.[A-Za-z]{2,}")


class EntityType(str, Enum):
    disease = "disease"
    gene = "gene"
    variant = "variant"
    transcript = "transcript"
    protein = "protein"
    phenotype = "phenotype"
    mechanism = "mechanism"
    finding = "finding"
    drug = "drug"
    study = "study"
    asset = "asset"
    organization = "organization"
    investigator = "investigator"


# Ensembl stable IDs encode their kind (ENSG gene, ENST transcript, ENSP protein).
_ENSEMBL_KIND = {"gene": "G", "transcript": "T"}

# Which namespaces may identify which entity type. UNRESOLVED is allowed for every type.
ENTITY_PREFIXES: dict[EntityType, frozenset[str]] = {
    EntityType.disease: frozenset({"MONDO", "ORPHA"}),
    EntityType.gene: frozenset({"HGNC", "NCBIGene", "ENSEMBL"}),
    EntityType.variant: frozenset({"VARIANT"}),
    EntityType.transcript: frozenset({"TRANSCRIPT", "ENSEMBL"}),
    EntityType.protein: frozenset({"UniProtKB"}),
    EntityType.phenotype: frozenset({"HP"}),
    EntityType.mechanism: frozenset({"REACT", "GO"}),
    EntityType.finding: frozenset({"FINDING"}),
    EntityType.drug: frozenset({"CHEBI"}),
    EntityType.study: frozenset({"STUDY", "PMID", "NCT"}),
    EntityType.asset: frozenset({"ASSET"}),
    EntityType.organization: frozenset({"ORG"}),
    EntityType.investigator: frozenset({"INV", "ORCID"}),
}


class IdentityStatus(str, Enum):
    resolved = "resolved"
    unresolved = "unresolved"
    ambiguous = "ambiguous"


class AssetKind(str, Enum):
    registry = "registry"
    natural_history_study = "natural_history_study"
    animal_model = "animal_model"
    cell_model = "cell_model"
    biomarker = "biomarker"
    biobank = "biobank"
    clinical_study = "clinical_study"  # added 2026-10-03: ClinicalTrials.gov records (DECISIONS.md)


_VERSIONED_HGVS = re.compile(r"[A-Z]{2}_\d+\.\d+:[cgnpr]\..+")


class Entity(BaseModel):
    """SQLite table `entities`. Unresolved/ambiguous identities stay unresolved (T03)."""

    model_config = _STRICT

    id: str
    schema_version: SchemaVersion = SCHEMA_VERSION
    type: EntityType
    label: str = Field(min_length=1)
    identity_status: IdentityStatus = IdentityStatus.resolved
    candidate_ids: tuple[CurieStr, ...] = ()  # resolver candidates; never merged into `id`
    synonyms: tuple[str, ...] = ()
    xrefs: tuple[CurieStr, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_url: str = Field(min_length=1)  # where identity/label came from
    source_type: SourceType
    source_version: str | None = None  # ontology/database release
    retrieved_at: date
    review_state: ReviewState = ReviewState.unreviewed

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        return validate_curie(v)

    @model_validator(mode="after")
    def _identity(self) -> Entity:
        prefix = self.id.partition(":")[0]
        if prefix == "SYN" and self.source_type is not SourceType.synthetic_fixture:
            raise ValueError("SYN: ids are reserved for synthetic records")
        if prefix == "SYN":
            pass
        elif self.identity_status is IdentityStatus.resolved:
            if prefix == "UNRESOLVED":
                raise ValueError("a resolved entity needs a real identifier")
            if prefix not in ENTITY_PREFIXES[self.type]:
                raise ValueError(f"{prefix}: is not a valid namespace for {self.type.value}")
            kind = _ENSEMBL_KIND.get(self.type.value)
            if prefix == "ENSEMBL" and not re.match(rf"ENS[A-Z]*{kind}\d", self.id[8:]):
                raise ValueError(f"{self.id} is not an Ensembl {self.type.value} ID")
            if self.candidate_ids:
                raise ValueError("a resolved entity carries no candidate_ids")
        else:
            if prefix != "UNRESOLVED":
                raise ValueError("unresolved/ambiguous entities must use an UNRESOLVED: id")
            if self.identity_status is IdentityStatus.ambiguous and len(self.candidate_ids) < 2:
                raise ValueError("ambiguous identity needs at least two candidate_ids")
        self._check_attributes()
        return self

    def _check_attributes(self) -> None:
        a = self.attributes
        if self.type is EntityType.variant and self.identity_status is IdentityStatus.resolved:
            if not a.get("assembly"):
                raise ValueError("variant attributes require an assembly")
            if not _VERSIONED_HGVS.fullmatch(str(a.get("hgvs", ""))):
                raise ValueError("variant attributes require HGVS on a versioned transcript")
        if self.type is EntityType.asset and a.get("asset_kind") not in {k.value for k in AssetKind}:
            raise ValueError("asset attributes require a known asset_kind")
        if _has_personal_contact(a):
            raise ValueError("no personal contact data in attributes; public URLs only")


def _has_personal_contact(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_EMAIL.search(value)) or "mailto:" in value
    if isinstance(value, dict):
        return any(_has_personal_contact(v) for v in (*value.keys(), *value.values()))
    if isinstance(value, (list, tuple)):
        return any(_has_personal_contact(v) for v in value)
    return False


class SourceStatus(str, Enum):
    ok = "ok"
    failed = "failed"
    unavailable = "unavailable"
    not_queried = "not_queried"


class SourceCoverage(BaseModel):
    """Counts are recorded by the pipeline step; None means not recorded, never 0."""

    model_config = _STRICT

    source: str = Field(min_length=1)
    version: str | None = None
    status: SourceStatus
    fetched: int | None = Field(default=None, ge=0)
    screened: int | None = Field(default=None, ge=0)
    error: str | None = None

    @model_validator(mode="after")
    def _counts(self) -> SourceCoverage:
        if self.status is SourceStatus.ok and (self.fetched is None or self.screened is None):
            raise ValueError("an ok source must record fetched and screened counts")
        if self.status in (SourceStatus.unavailable, SourceStatus.not_queried) and (
            self.fetched is not None or self.screened is not None
        ):
            raise ValueError("a source that was not queried has no counts (None, not 0)")
        if self.status is SourceStatus.failed and not self.error:
            raise ValueError("a failed source must record its error")
        if self.fetched is not None and self.screened is not None and self.screened > self.fetched:
            raise ValueError("screened cannot exceed fetched")
        return self


class ChannelCoverage(BaseModel):
    model_config = _STRICT

    channel_id: str = Field(min_length=1)
    availability: Availability
    note: str | None = None


class CoverageManifest(BaseModel):
    """One per search. Counts come from recorded operations, never generated text."""

    model_config = _STRICT

    manifest_id: str
    schema_version: SchemaVersion = SCHEMA_VERSION
    query: str
    dataset_version: str
    source_versions: dict[str, str] = Field(default_factory=dict)
    retrieved_at: datetime
    filters: dict[str, Any] = Field(default_factory=dict)
    per_source: tuple[SourceCoverage, ...]
    per_channel: tuple[ChannelCoverage, ...] = ()
    generated_by: str = Field(min_length=1)  # pipeline step + version that recorded the counts

    @field_validator("manifest_id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _prefixed(v, "COV")


# Statements must scope absence to the indexed evidence (PLAN "Coverage and honesty").
_GLOBAL_ABSENCE = re.compile(
    r"\b(no (treatments?|therap(y|ies)|cures?|registr(y|ies)) (exists?|(is|are) available)|"
    r"(does|do) not exist|there (is|are) no (treatments?|therap(y|ies)|cures?|registr(y|ies)))",
    re.IGNORECASE,
)


class GapResult(BaseModel):
    model_config = _STRICT

    kind: Literal[
        "insufficient_coverage",
        "unresolved_identity",
        "hypothesis_only",
        "conflicting_evidence",
        "no_supported_route",
    ]
    statement: str  # "No supported route found in the indexed evidence as of <date>"
    as_of: date
    entity_id: CurieStr | None = None
    coverage_manifest_id: str
    known_claim_ids: tuple[CurieStr, ...] = ()
    failed_sources: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = Field(min_length=1)  # what could change the result
    reviewer_role: str = Field(min_length=1)
    scope_note: str = "Research-support gap report. Absence is scoped to the indexed evidence."

    @field_validator("coverage_manifest_id")
    @classmethod
    def _cov(cls, v: str) -> str:
        return _prefixed(v, "COV")

    @model_validator(mode="after")
    def _honest(self) -> GapResult:
        if _GLOBAL_ABSENCE.search(self.statement):
            raise ValueError("gap statement asserts global absence; scope it to indexed evidence")
        if self.as_of.isoformat() not in self.statement:
            raise ValueError("gap statement must name its as-of date")
        return self


class Contact(BaseModel):
    """A public route only (organization page, contact form). Never personal data."""

    model_config = _STRICT

    label: str = Field(min_length=1)
    url: str
    source_url: str = Field(min_length=1)
    verified_at: date

    @field_validator("url")
    @classmethod
    def _public(cls, v: str) -> str:
        if not v.startswith("https://") or _EMAIL.search(v):
            raise ValueError("contact must be a public https URL, not an email address")
        return v


class AssetResult(BaseModel):
    """Ranked separately from biology: no evidence category, no biology score (PLAN rule)."""

    model_config = _STRICT

    asset_id: str
    asset_kind: AssetKind
    label: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    relevance_claim_ids: tuple[CurieStr, ...] = Field(min_length=1)  # ASSET_RELEVANT_TO claims
    access_conditions: str | None = None
    status: str | None = None  # e.g. "active", verbatim from the source
    status_source_url: str | None = None
    status_checked_at: date | None = None
    reuse_limits: tuple[str, ...] = ()  # species/tissue/eligibility differences
    contact: Contact | None = None
    needs_expert_review: tuple[str, ...] = ()
    ranking_reasons: tuple[str, ...] = ()  # practical reasons only (access, status, fit)

    @field_validator("asset_id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _prefixed(v, "ASSET")

    @model_validator(mode="after")
    def _status_sourced(self) -> AssetResult:
        if self.status is not None and not (self.status_source_url and self.status_checked_at):
            raise ValueError("asset status needs status_source_url and status_checked_at")
        return self


FOOTNOTE = re.compile(r"\[\^c:([^\]\s]+)\]")
_ANY_FOOTNOTE = re.compile(r"\[\^[^\]]*\]")
# Tripwire, not a guarantee: cards must never dose, prescribe or decide eligibility.
_CLINICAL = re.compile(
    r"\b(dos(e|es|ed|age|ages|ing)|\d+(\.\d+)?\s?mg\b|mg/kg|prescrib\w*|"
    r"should (take|start|stop)|(is|are) (in)?eligible|(in)?eligible for)\b",
    re.IGNORECASE,
)


class ActionCard(BaseModel):
    model_config = _STRICT

    card_id: str
    schema_version: SchemaVersion = SCHEMA_VERSION
    kind: Literal[
        "evidence_brief", "outreach_note", "asset_reuse", "gap_followup", "simulation_report"
    ]
    audience: Literal["family", "science"]
    entity_id: CurieStr | None = None
    this_week: str = Field(min_length=1)  # one concrete step
    responsible_human: str = Field(min_length=1)  # role that must review/send
    body_markdown: str  # footnotes [^c:<claim_id>]
    claim_ids: tuple[CurieStr, ...] = ()
    asset_ids: tuple[CurieStr, ...] = ()
    coverage_manifest_id: str | None = None
    reuse_limits: tuple[str, ...] = ()
    contact: Contact | None = None
    limitations: tuple[str, ...] = Field(min_length=1)
    generated_by: str  # "template" | "llm:<model>"
    cached: bool = False
    created_at: datetime | None = None

    @field_validator("card_id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _prefixed(v, "CARD")

    @field_validator("responsible_human")
    @classmethod
    def _human(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a responsible human role is required")
        return v

    @field_validator("generated_by")
    @classmethod
    def _gen(cls, v: str) -> str:
        if v != "template" and not re.fullmatch(r"llm:\S+", v):
            raise ValueError("generated_by must be 'template' or 'llm:<model>'")
        return v

    @model_validator(mode="after")
    def _traceable(self) -> ActionCard:
        malformed = [f for f in _ANY_FOOTNOTE.findall(self.body_markdown) if not FOOTNOTE.fullmatch(f)]
        if malformed:
            raise ValueError(f"footnotes must use [^c:<claim_id>]: {malformed}")
        cited = set(FOOTNOTE.findall(self.body_markdown))
        dangling = cited - set(self.claim_ids)
        if dangling:
            raise ValueError(f"footnotes cite claims not in claim_ids: {sorted(dangling)}")
        texts = [self.body_markdown, self.this_week, *self.limitations, *self.reuse_limits]
        if self.contact:
            texts.append(self.contact.label)
        if any(_CLINICAL.search(t) for t in texts):
            raise ValueError("action card contains clinical directive language")
        if self.kind == "asset_reuse" and not self.asset_ids:
            raise ValueError("an asset_reuse card must reference asset_ids")
        return self
