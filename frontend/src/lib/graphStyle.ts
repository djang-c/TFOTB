import type { GraphEdge } from "@/lib/api";
import { HYPOTHESIS_PREDICATES } from "@/lib/labels";

export { clean } from "@/lib/labels";

/** An edge that rests on a hypothesis (an AI proposal or a hypothesis-only relationship), never on a finding. */
export const isHypothesisEdge = (e: Pick<GraphEdge, "predicate" | "status">) =>
  HYPOTHESIS_PREDICATES.has(e.predicate) || e.status === "inference";

export const edgeKey = (e: GraphEdge) => e.claim_id ?? `${e.source}|${e.target}|${e.predicate}`;
