// Typed client for the TFOTB API (src/atlas/api). Shapes mirror src/atlas/schemas.py and the routes in
// src/atlas/api/routes.py. Nothing here is bundled data: every screen reads from the running API.

export const API_BASE = (
  (import.meta.env["VITE_API_BASE"] as string | undefined) ?? "http://localhost:8000/api"
).replace(/\/$/, "");

export type EntityType =
  | "disease"
  | "gene"
  | "variant"
  | "transcript"
  | "protein"
  | "phenotype"
  | "mechanism"
  | "finding"
  | "drug"
  | "study"
  | "asset"
  | "organization"
  | "investigator"
  | "term";

export type SourceType =
  "published" | "database_record" | "lab_reported" | "synthetic_fixture" | "ai_generated";
export type ReviewState = "unreviewed" | "reviewed" | "disputed";
export type ClaimStatus = "reported_observation" | "computational_prediction" | "inference";

export interface Entity {
  id: string;
  type: EntityType;
  label: string;
  identity_status: "resolved" | "unresolved" | "ambiguous";
  synonyms: string[];
  attributes: Record<string, unknown>;
  source_url: string;
  source_type: SourceType;
  source_version: string | null;
  retrieved_at: string;
  review_state: ReviewState;
}

export interface Claim {
  claim_id: string;
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
  schema_version: string;
}

export type Availability = "available" | "missing" | "incompatible" | "failed";

export interface ChannelComparison {
  channel_id: string;
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
  | "reviewed mechanistic lead"
  | "literature-supported lead"
  | "symptom-level lead"
  | "hypothesis only"
  | "conflicting evidence"
  | "insufficient coverage";

export interface ConnectionResult {
  candidate_id: string;
  comparisons: ChannelComparison[];
  category: EvidenceCategory;
  compatibility_flags: string[];
  path_claim_ids: string[];
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

export interface Contact {
  label: string;
  url: string;
  verified_at: string;
}

export interface AssetResult {
  asset_id: string;
  asset_kind: string;
  label: string;
  source_url: string;
  relevance_claim_ids: string[];
  access_conditions: string | null;
  status: string | null;
  reuse_limits: string[];
  contact: Contact | null;
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
}

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
}
export interface GraphEdge {
  source: string;
  target: string;
  predicate: string;
  /** null for computed links (symptom similarity): never shown as sourced. */
  claim_id: string | null;
  status: ClaimStatus;
  review_state: ReviewState;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  omitted: number;
}

export interface SearchHit {
  id: string;
  label: string;
  type: EntityType;
  matched: string | null;
  match?: string;
  source_type?: SourceType;
  added_by_lookup?: boolean;
}

export interface TermPaper {
  pmid: string;
  title: string;
  journal: string;
  year: string;
  doi: string | null;
  url: string;
}

export type LookupResult =
  | { status: "rejected"; reason: string; stored: false }
  | { status: "known"; query: string; reason: string; results: SearchHit[]; stored: false }
  | {
      status: "added";
      query: string;
      reason: string;
      entity_id: string;
      label: string;
      kind: string | null;
      verified_by: string | null;
      papers: TermPaper[];
      persisted: boolean;
      note: string;
      stored: true;
      sources_checked: { source: string; status: string; found: number | boolean | null }[];
    }
  | {
      status: "not_verified" | "not_medical" | "unavailable";
      query: string;
      reason: string;
      label: string | null;
      stored: false;
      sources_checked: { source: string; status: string; found: number | boolean | null }[];
    };

export interface Related {
  entity_id: string;
  groups: {
    kind: string;
    title: string;
    source: string;
    total: number;
    items: {
      id: string;
      label: string;
      type: EntityType;
      association?: string;
      source_id?: string;
      score?: number | null;
      shared?: string[];
    }[];
  }[];
}

export interface PatientGroups {
  status: "ok" | "failed" | "no_xref" | "not_a_disease" | "not_available";
  note?: string;
  retrieved?: string;
  pages: { label: string; url: string }[];
  groups: {
    name: string;
    website: string | null;
    country: string | null;
    registry_url: string | null;
  }[];
}

export interface SymptomSearch {
  terms: {
    text: string;
    status: string;
    id: string | null;
    label: string;
    candidates?: { id: string; label: string }[];
  }[];
  candidates: {
    disease_id: string;
    label: string;
    coverage: number;
    profile_share: number;
    recorded_symptoms: number;
    matched_labels: string[];
    unmatched_labels: string[];
    recorded_absent: string[];
    genes: { id: string; label: string; claim_id: string; source: string }[];
  }[];
  definition: string;
  note: string;
}

export interface Collaborators {
  items: {
    name: string;
    orcid: string | null;
    affiliation: string | null;
    match: string;
    other_papers: number;
    papers: {
      source_id: string;
      title: string;
      journal: string;
      year: string;
      citation: string;
      claim_ids: string[];
    }[];
    also_studies: { entity_id: string; label: string; claim_ids: string[] }[];
  }[];
  total: number;
  bridges: number;
  papers_considered: number;
  note: string;
}

export interface Cluster {
  diseases: { id: string; label: string }[];
  shared_features: {
    feature: string;
    label: string;
    diseases: string[];
    claim_ids: string[];
    studies: number;
  }[];
}

export interface Routes {
  source: string;
  target: string;
  paths: {
    nodes: { id: string; label: string }[];
    hops: { a: string; b: string; claim_ids: string[]; hypothesis_only: boolean }[];
    hypothesis_only: boolean;
    reviewed_claims: number;
    shared_feature_stops: { id: string; label: string }[];
  }[];
  gap: GapResult | null;
}

export interface Meta {
  dataset_version: string;
  featured?: { id: string; label: string; type: EntityType }[];
  simulations?: { run_id: string; label: string; spec?: string; overall?: "pass" | "fail" }[];
  real?: {
    counts: Record<"disease" | "gene" | "phenotype", number>;
    names: number;
    seed: { id: string; label: string; type: EntityType }[];
    seed_note: string;
  } | null;
  store?: {
    claims: number;
    papers: number;
    ai_hypotheses: number;
    treatment_ideas: number;
    terms_added: number;
  };
}

export interface SimRun {
  run_id: string;
  label: string;
  spec: string;
  graph_link?: Claim | null;
  linked_entity?: { id: string; label: string } | null;
  trajectory: { scope_label: string; units: string; points: [number, number, number][] };
  report: {
    overall: "pass" | "fail";
    scope_label: string;
    simulator_name: string;
    simulator_version: string;
    review_state: string;
    checks: { check_name: string; status: "pass" | "fail" | "not_modeled"; reason: string }[];
    failures: { op_index?: number; check: string; reason: string }[];
    operation_trace: {
      op_index: number;
      op: string;
      status: string;
      end_mm: [number, number, number];
    }[];
    ledger_after: {
      source_ul: number;
      tips_available: number;
      tip_attached: boolean;
      held_ul: number;
      wells_ul: Record<string, number>;
    };
    path_length_mm: number;
  };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "The API could not be reached.");
  }
  if (!res.ok) throw new ApiError(res.status, `${res.status} on ${path}`);
  return (await res.json()) as T;
}

export const enc = (id: string) => encodeURIComponent(id);

export const api = {
  health: () => request<{ status: string }>("/health"),
  ready: () => request<{ ready: boolean; index: string }>("/ready"),
  meta: () => request<Meta>("/meta"),
  search: (q: string) =>
    request<{ results: SearchHit[]; ambiguous?: boolean }>(`/search?q=${enc(q)}`),
  lookup: (query: string) =>
    request<LookupResult>("/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }),
  entity: (id: string) =>
    request<{
      entity: Entity;
      claims: Claim[];
      summary: { text: string; claim_ids: string[]; source?: string }[];
      summary_method?: string;
      papers?: TermPaper[];
      verification?: { by: string; reason: string };
    }>(`/entities/${enc(id)}`),
  connections: (id: string) =>
    request<{
      results: ConnectionResult[];
      coverage: CoverageManifest | null;
      labels?: Record<string, string>;
      hierarchy?: Record<string, string>;
    }>(`/entities/${enc(id)}/connections`),
  related: (id: string) => request<Related>(`/entities/${enc(id)}/related`),
  assets: (id: string) =>
    request<{ assets: AssetResult[]; total?: number | null }>(`/entities/${enc(id)}/assets`),
  groups: (id: string) => request<PatientGroups>(`/entities/${enc(id)}/groups`),
  collaborators: (id: string) => request<Collaborators>(`/entities/${enc(id)}/collaborators`),
  graph: (id: string, maxNodes = 40) =>
    request<GraphData>(`/entities/${enc(id)}/graph?max_nodes=${maxNodes}`),
  routes: (id: string, to: string) => request<Routes>(`/entities/${enc(id)}/routes?to=${enc(to)}`),
  gap: (id: string) =>
    request<{ gap: GapResult | null; coverage: CoverageManifest | null }>(
      `/entities/${enc(id)}/gap`,
    ),
  actions: (id: string) => request<{ cards: ActionCard[] }>(`/entities/${enc(id)}/actions`),
  claim: (id: string) =>
    request<{
      claim: Claim;
      subject_label: string | null;
      object_label: string | null;
      lineage_siblings: string[];
      contradicting_claims: string[];
    }>(`/claims/${enc(id)}`),
  symptoms: (q: string) => request<SymptomSearch>(`/symptoms?q=${enc(q)}`),
  clusters: () => request<{ clusters: Cluster[]; total: number; note: string }>("/clusters"),
  simulation: (id: string) => request<SimRun>(`/simulations/${enc(id)}`),
};
