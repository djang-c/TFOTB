# 03 — Data & API Contracts

Implements: T02 (remaining), API surface for T09–T12. The core contracts already exist in
`src/atlas/schemas.py` (`Claim`, `ChannelComparison`, `ConnectionResult`, enums). This doc adds what
is missing and defines the HTTP API on top. It does **not** reintroduce evidence tiers or a numeric
confidence — PLAN replaced both with independent dimensions.

## 1. What already exists (don't redefine)

- `Claim`: subject/object CURIEs, allowed predicate, `source_url`, `source_span`, `source_type`
  (published | database_record | lab_reported | synthetic_fixture), `status` (reported_observation
  | computational_prediction | inference), `review_state`, `lineage_id`, `context`, `contradicts`,
  optional `score` + required `score_definition`.
- `ChannelComparison`: per-channel `availability`, nullable `score`, supporting/contradicting claim
  IDs, context matches/mismatches, missing fields, limitations.
- `ConnectionResult`: comparisons + `EvidenceCategory` + compatibility flags + path claim IDs +
  coverage manifest ID + `shared_treatment_inference_allowed`.
- `validate_curie`: rejects label-built IDs.

## 2. To add in T02

```python
class EntityType(str, Enum):
    disease, gene, variant, transcript, protein, phenotype, mechanism,
    finding, drug, study, asset, organization, investigator

class Entity(BaseModel):            # SQLite table `entities`
    id: str                         # validated CURIE or scoped internal ID
    type: EntityType
    label: str
    synonyms: list[str] = []
    xrefs: list[str] = []
    attributes: dict[str, Any]      # type-specific (below)
    source_url: str                 # where identity/label came from
    retrieved_at: date

class CoverageManifest(BaseModel):  # one per search; counts from recorded operations only
    manifest_id: str
    query: str
    source_versions: dict[str, str]
    retrieved_at: datetime
    filters: dict[str, Any]
    per_source: list[{source, fetched: int, screened: int, status: ok|failed|unavailable}]

class GapResult(BaseModel):
    kind: Literal["insufficient_coverage","unresolved_identity","hypothesis_only",
                  "conflicting_evidence","no_supported_route"]
    statement: str                  # "No supported route found in the indexed evidence as of <date>"
    coverage_manifest_id: str
    known_claim_ids: list[str]
    missing_information: list[str]  # what could change the result
    reviewer_role: str              # who should review

class AssetResult(BaseModel):       # ranked separately from biology (PLAN rule)
    asset_id: str
    relevance_claim_ids: list[str]  # ASSET_RELEVANT_TO claims
    access_conditions: str | None
    status: str | None              # active / unknown, with source
    reuse_limits: list[str]         # species/tissue/eligibility differences
    contact: {label, url, verified_at} | None   # public route only; never personal data
    needs_expert_review: list[str]

class ActionCard(BaseModel):
    card_id: str
    kind: Literal["evidence_brief","outreach_note","asset_reuse","gap_followup",
                  "simulation_report"]            # P1: aso_checklist, repurposing_paths
    this_week: str                  # one concrete step
    responsible_human: str          # role that must review/send
    body_markdown: str              # footnotes reference claim IDs
    claim_ids: list[str]
    limitations: list[str]
    generated_by: str               # "template" | "llm:<model>" (+ cached flag)
```

Type-specific `Entity.attributes`: variant (assembly, HGVS with transcript version, alleles,
zygosity, `is_synthetic`); phenotype (IC + corpus version); asset (kind: registry |
natural_history_study | animal_model | cell_model | biomarker | biobank; data fields; access);
organization (website, verified public contact URL, verified_at).

## 3. UI display mapping (replaces "tiers")

| Dimension | Values → display |
|---|---|
| `source_type` | published → "Published"; database_record → "Database record"; lab_reported → "Lab-reported" (yellow badge); synthetic_fixture → "SYNTHETIC" (always visible) |
| `status` | reported_observation → solid edge; computational_prediction → dashed + "Prediction"; inference → dotted purple + "Hypothesis" |
| `review_state` | reviewed → ✓; unreviewed → "Unreviewed"; disputed → ⚠ |
| contradictions | ⚠ marker; drawer lists contradicting claims |
| `EvidenceCategory` | Pill on each connection: reviewed mechanistic lead / symptom-level lead / hypothesis only / conflicting evidence / insufficient coverage |
| channel availability | Per-channel chip: ✓ available, — missing (score shown as "no data", never 0), ✕ incompatible, ! failed |

## 4. HTTP API (`/api`)

| Method & path | Purpose | Response |
|---|---|---|
| `GET /search?q=` | Resolve disease/gene/variant/symptom/mechanism/org | `{resolved: Entity\|null, candidates[{entity, matched_on, match_text}], ambiguous: bool}` |
| `GET /entities/{id}` | Entity detail | `{entity, claim_counts_by_predicate}` |
| `GET /entities/{id}/connections` | Maria Q1: related diseases | `{results: ConnectionResult[], coverage: CoverageManifest}` |
| `GET /claims/{claim_id}` | Evidence drawer | `Claim` + lineage siblings + contradicting claims |
| `GET /entities/{id}/assets` | Maria Q2: reusable work | `{assets: AssetResult[]}` |
| `GET /entities/{id}/collaborators` | Shared investigators / network overlap | `{items[{investigator, claim_ids_per_disease}]}` |
| `GET /entities/{id}/graph?max_nodes=40` | Optional canvas | `{nodes, edges(claim_id per edge), truncated, omitted}` |
| `POST /explain` | Grounded plain language | req `{claim_ids[], audience}` → `{sentences[{text, claim_ids[]}], dropped: int, cached: bool}` |
| `GET /entities/{id}/gap` | Honest gap | `GapResult` |
| `POST /actions` | Maria Q3: next step | req `{kind, entity_id, context}` → `ActionCard` |
| `POST /uploads` | Lab finding (T11) | `{claim\|null, quarantined: bool, unresolved_ids[], missing_fields[]}` — always lab_reported + unreviewed |
| `GET /simulations/{run_id}` | Robotics report (T23) | `SimulationRun` (+ replay URL, scope label) |
| `GET /meta` | Versions & counts | dataset/schema versions, source versions, counts by source_type / review_state |

Private/synthetic case endpoints (T15) live under `/api/cases/*` and are never reachable from
`/search` or `/entities/*` — covered by the existing privacy test pattern.

## 5. Fixtures

`data/fixtures/` holds JSON responses for the PLAN fixture cases (positive route, symptom-only,
opposing mechanism, missing RNA, uncertain variant, contradiction, no-route), all `SYNTHETIC` until
T01 supplies reviewed biology. Backend contract tests and frontend mock mode read the same files.
