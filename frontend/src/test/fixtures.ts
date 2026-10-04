import type { Claim } from "@/lib/api";

export const claim = (over: Partial<Claim> = {}): Claim => ({
  claim_id: "CLAIM:PMID-1-aaaa",
  subject_id: "CHEBI:50381",
  predicate: "CANDIDATE_THERAPY_FOR",
  object_id: "MONDO:0018982",
  source_url: "https://doi.org/10.1/abc",
  source_span: "Miglustat is a licensed therapy.",
  source_type: "published",
  status: "inference",
  review_state: "unreviewed",
  lineage_id: "STUDY:PMID-1",
  context: {},
  contradicts: [],
  score: null,
  score_definition: null,
  contributor: null,
  published_at: "2024-01-01",
  retrieved_at: null,
  extraction_method: "llm:some-model@extract-v5",
  review_notes: [],
  derived_from: [],
  knowledge_level: "observation",
  schema_version: "0.2.0",
  ...over,
});

/** Replace fetch with a router: the first matching [pattern, body] answers; anything else is a 404. */
export function mockApi(routes: [RegExp, unknown | ((init?: RequestInit) => unknown)][]) {
  const calls: { url: string; init?: RequestInit | undefined }[] = [];
  globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    const hit = routes.find(([re]) => re.test(u));
    if (!hit) return new Response("{}", { status: 404 });
    const body =
      typeof hit[1] === "function" ? (hit[1] as (i?: RequestInit) => unknown)(init) : hit[1];
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  return calls;
}
