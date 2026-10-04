import type { Availability, ClaimStatus, EvidenceCategory, ReviewState, SourceType } from "@/lib/api";

const base = "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium whitespace-nowrap";

export function SourceBadge({ type }: { type: SourceType }) {
  const map: Record<SourceType, [string, string]> = {
    published: ["Published", "bg-link-soft text-link"],
    database_record: ["Database record", "bg-link-soft text-link"],
    lab_reported: ["Lab-reported", "bg-lab text-ink ring-1 ring-[#e0c64a]"],
    synthetic_fixture: ["Synthetic", "bg-synthetic/40 text-ink ring-1 ring-synthetic"],
    ai_generated: ["AI hypothesis", "text-ev-hypo ring-1 ring-ev-hypo bg-white"],
  };
  const [label, cls] = map[type];
  return <span className={`${base} ${cls}`}>{label}</span>;
}

export function ReviewBadge({ state }: { state: ReviewState }) {
  if (state === "reviewed") return <span className={`${base} bg-ev-reviewed/10 text-ev-reviewed`}>✓ Reviewed</span>;
  if (state === "disputed") return <span className={`${base} bg-ev-conflict/10 text-ev-conflict`}>⚠ Disputed</span>;
  return <span className={`${base} bg-rule/60 text-muted`}>Unreviewed</span>;
}

export const STATUS_LABEL: Record<ClaimStatus, string> = {
  reported_observation: "Reported observation",
  computational_prediction: "Computational prediction",
  inference: "Inference",
};

/** Line style mirrors the graph: solid observation, dashed prediction, dotted inference. */
export function StatusMark({ status }: { status: ClaimStatus }) {
  const style = status === "reported_observation" ? "solid" : status === "computational_prediction" ? "dashed" : "dotted";
  const color = status === "inference" ? "var(--color-ev-hypo)" : "var(--color-ink)";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className="inline-block w-5" style={{ borderTop: `2px ${style} ${color}` }} />
      {STATUS_LABEL[status]}
    </span>
  );
}

const CATEGORY: Record<EvidenceCategory, string> = {
  "reviewed mechanistic lead": "bg-ev-reviewed text-white",
  "literature-supported lead": "bg-ev-literature text-white",
  "symptom-level lead": "bg-ev-symptom text-white",
  "hypothesis only": "text-ev-hypo ring-1 ring-ev-hypo bg-white",
  "conflicting evidence": "bg-ev-conflict text-white",
  "insufficient coverage": "bg-ev-gap text-white",
};

export function CategoryPill({ category }: { category: EvidenceCategory }) {
  const icon = category === "conflicting evidence" ? "⚠ " : "";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${CATEGORY[category]}`}>
      {icon}
      {category.charAt(0).toUpperCase() + category.slice(1)}
    </span>
  );
}

export const AVAILABILITY_TEXT: Record<Availability, string> = {
  available: "available",
  missing: "no data",
  incompatible: "incompatible",
  failed: "source failed",
};

export const GAP_KIND: Record<string, string> = {
  insufficient_coverage: "Insufficient coverage",
  unresolved_identity: "Unresolved identity",
  hypothesis_only: "Hypothesis only",
  conflicting_evidence: "Conflicting evidence",
  no_supported_route: "No supported route",
};
