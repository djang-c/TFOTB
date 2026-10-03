// Typed client for the TFOTB API. Shapes mirror src/atlas/schemas.py (0.2.0) and the stub
// routes in src/atlas/api/routes.py. Everything served today is SYNTHETIC.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

export type EntityType =
  | "disease" | "gene" | "variant" | "transcript" | "protein" | "phenotype" | "mechanism"
  | "finding" | "drug" | "study" | "asset" | "organization" | "investigator";

export interface Entity {
  id: string;
  type: EntityType;
  label: string;
  identity_status: "resolved" | "unresolved" | "ambiguous";
  candidate_ids: string[];
  synonyms: string[];
  xrefs: string[];
  attributes: Record<string, unknown>;
  source_url: string;
  source_type: SourceType;
  source_version: string | null;
  retrieved_at: string;
  review_state: ReviewState;
}

export type SourceType = "published" | "database_record" | "lab_reported" | "synthetic_fixture";
export type ReviewState = "unreviewed" | "reviewed" | "disputed";
export type ClaimStatus = "reported_observation" | "computational_prediction" | "inference";

export interface Claim {
  claim_id: string;
  schema_version: string;
  subject_id: string;
  predicate: string;
  object_id: string;
  source_url: string;
  source_span: string;
  source_type: SourceType;
  status: ClaimStatus;
  review_state: ReviewState;
  lineage_id: string;
  context: Record<string, string>;
  contradicts: string[];
  score: number | null;
  score_definition: string | null;
  contributor: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  extraction_method: string | null;
  review_notes: string[];
  derived_from: string[];
  knowledge_level: string;
  agent_type: string;
}

export type Availability = "available" | "missing" | "incompatible" | "failed";

export interface ChannelComparison {
  channel_id: string;
  candidate_id: string;
  availability: Availability;
  score: number | null;
  score_definition: string | null;
  supporting_claim_ids: string[];
  contradicting_claim_ids: string[];
  context_matches: string[];
  context_mismatches: string[];
  missing_fields: string[];
  limitations: string[];
}

export type EvidenceCategory =
  | "reviewed mechanistic lead" | "symptom-level lead" | "hypothesis only"
  | "conflicting evidence" | "insufficient coverage";

export interface ConnectionResult {
  candidate_id: string;
  comparisons: ChannelComparison[];
  category: EvidenceCategory;
  compatibility_flags: string[];
  path_claim_ids: string[];
  coverage_manifest_id: string | null;
  shared_treatment_inference_allowed: boolean;
  scope_note: string;
}

export interface SourceCoverage {
  source: string;
  version: string | null;
  status: "ok" | "failed" | "unavailable" | "not_queried";
  fetched: number | null;
  screened: number | null;
  error: string | null;
}

export interface CoverageManifest {
  manifest_id: string;
  query: string;
  dataset_version: string;
  retrieved_at: string;
  per_source: SourceCoverage[];
  per_channel: { channel_id: string; availability: Availability; note: string | null }[];
  generated_by: string;
}

export interface GapResult {
  kind: string;
  statement: string;
  as_of: string;
  known_claim_ids: string[];
  failed_sources: string[];
  missing_information: string[];
  reviewer_role: string;
  scope_note: string;
}

export interface Contact { label: string; url: string; source_url: string; verified_at: string }

export interface AssetResult {
  asset_id: string;
  asset_kind: string;
  label: string;
  source_url: string;
  relevance_claim_ids: string[];
  access_conditions: string | null;
  status: string | null;
  status_checked_at: string | null;
  reuse_limits: string[];
  contact: Contact | null;
  needs_expert_review: string[];
  ranking_reasons: string[];
}

export interface ActionCard {
  card_id: string;
  kind: "evidence_brief" | "outreach_note" | "asset_reuse" | "gap_followup" | "simulation_report";
  audience: "family" | "science";
  this_week: string;
  responsible_human: string;
  body_markdown: string;
  claim_ids: string[];
  contact: Contact | null;
  reuse_limits: string[];
  limitations: string[];
  generated_by: string;
  cached: boolean;
}

export interface GraphData {
  nodes: { id: string; label: string; type: EntityType }[];
  edges: { source: string; target: string; predicate: string; claim_id: string; status: ClaimStatus; review_state: ReviewState }[];
  truncated: boolean;
  omitted: number;
}

export interface SimRun {
  run_id: string;
  label: string;
  spec: string;
  scene: { name: string; pos: number[]; size: number[]; collides: boolean }[];
  trajectory: { scope_label: string; units: string; points: number[][] };
  report: {
    overall: "pass" | "fail";
    scope_label: string;
    simulator_name: string;
    simulator_version: string;
    experiment_spec_hash: string;
    scene_hash: string;
    review_state: string;
    checks: { check_name: string; status: "pass" | "fail" | "not_modeled"; reason: string }[];
    failures: { op_index?: number; check: string; reason: string }[];
    ledger_before: Record<string, unknown>;
    ledger_after: Record<string, unknown>;
    path_length_mm: number;
  };
}

type Wrapped<T> = T & { _synthetic: string };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function get<T>(path: string): Promise<Wrapped<T>> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new ApiError(res.status, `${res.status} on ${path}`);
  return res.json();
}

export const enc = (id: string) => encodeURIComponent(id);

export type MatchKind = "identifier" | "label" | "exact synonym" | "related synonym" | "all words" | "close spelling" | "demo";

/** One search match. `matched` is the label or synonym text that matched; `match` says how. */
export interface SearchHit {
  id: string;
  label: string;
  type: EntityType;
  matched: string | null;
  match?: MatchKind;
  source_type?: SourceType;
}

export interface RelatedItem {
  id: string;
  label: string;
  type: EntityType;
  association?: string;
  source_id?: string;
  score?: number | null;
  shared?: string[];
}

/** What connects to an entry in the pinned files. Each group names the source it came from. */
export interface Related {
  entity_id: string;
  groups: { kind: string; title: string; source: string; total: number; items: RelatedItem[] }[];
}

/** The real-ontology layer, present when the pinned files are loaded. */
export interface RealMeta {
  counts: Record<"disease" | "gene" | "phenotype", number>;
  names: number;
  sources: Record<string, string>;
  seed: { id: string; label: string; type: EntityType; related: Record<string, number> }[];
  seed_note: string;
}

/** A home-page entry point. The API derives these from the dataset; they are never hand-picked. */
export type Featured = { id: string; label: string; type: EntityType } & (
  | { reason: "connections"; connections: number; assets: number }
  | { reason: "gap"; gap_kind: string }
);

export const api = {
  meta: () => get<{ dataset_version: string; as_of: string; schema_version: string;
    entities_by_type: Record<string, number>; claims: number;
    counts_by_review_state: Record<string, number>; counts_by_source_type: Record<string, number>;
    featured?: Featured[]; simulations?: { run_id: string; label: string }[]; real?: RealMeta | null }>("/meta"),
  search: (q: string) => get<{ results: SearchHit[]; ambiguous?: boolean }>(`/search?q=${enc(q)}`),
  related: (id: string) => get<Related>(`/entities/${enc(id)}/related`),
  entities: () => get<{ items: Entity[] }>("/entities"),
  entity: (id: string) => get<{ entity: Entity; claims: Claim[]; claim_counts_by_predicate: Record<string, number>;
    reviewed_claims: number; summary: { text: string; claim_ids: string[] }[] }>(`/entities/${enc(id)}`),
  connections: (id: string) => get<{ results: ConnectionResult[]; coverage: CoverageManifest | null }>(`/entities/${enc(id)}/connections`),
  assets: (id: string) => get<{ assets: AssetResult[] }>(`/entities/${enc(id)}/assets`),
  graph: (id: string) => get<GraphData>(`/entities/${enc(id)}/graph`),
  gap: (id: string) => get<{ gap: GapResult | null; coverage: CoverageManifest | null }>(`/entities/${enc(id)}/gap`),
  actions: (id: string) => get<{ cards: ActionCard[] }>(`/entities/${enc(id)}/actions`),
  claim: (id: string) => get<{ claim: Claim; subject_label: string | null; object_label: string | null;
    lineage_siblings: string[]; contradicting_claims: string[] }>(`/claims/${enc(id)}`),
  simulation: (id: string) => get<SimRun>(`/simulations/${enc(id)}`),
};
