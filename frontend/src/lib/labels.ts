// Plain-language wording and origin labels. Every rule here exists so the page never claims more than the data does:
// an AI finding is labelled as one, a hypothesis is never shown as a finding, and a drug is a "treatment idea".

import type { Claim, EvidenceCategory } from "@/lib/api";

/** Plain-language reading of each relationship. Wording never claims more than the predicate does. */
export const PREDICATE_PLAIN: Record<string, string> = {
  AFFECTS_TRANSCRIPT: "affects the RNA transcript",
  ASSOCIATED_WITH_PHENOTYPE: "is reported with the symptom",
  HAS_OBSERVED_RNA_EFFECT: "has an observed RNA effect on",
  HAS_PREDICTED_RNA_EFFECT: "is predicted (not observed) to have an RNA effect on",
  PERTURBS_MECHANISM: "disrupts the biological process",
  SUPPORTED_BY: "is supported by",
  CONTRADICTED_BY: "is contradicted by",
  INVESTIGATED_IN: "was studied in",
  ASSET_RELEVANT_TO: "lists as a condition",
  SIMULATES_WORKFLOW_FOR: "simulates a lab workflow (engineering only) for",
  GENE_ASSOCIATED_WITH_DISEASE: "is linked to",
  ACCUMULATES_IN_COMPARTMENT: "shows build-up in",
  SHARES_PATHOGENIC_PATHWAY_WITH: "may share a disease process with",
  CANDIDATE_THERAPY_FOR: "is a treatment idea (not a recommendation) for",
};

export const plain = (predicate: string) =>
  PREDICATE_PLAIN[predicate] ?? predicate.toLowerCase().replaceAll("_", " ");

/** Relationships recorded as hypotheses only, never as findings. */
export const HYPOTHESIS_PREDICATES = new Set([
  "SHARES_PATHOGENIC_PATHWAY_WITH",
  "CANDIDATE_THERAPY_FOR",
]);

export const isDrugClaim = (c: Pick<Claim, "predicate">) => c.predicate === "CANDIDATE_THERAPY_FOR";

/** The AI model named in the claim's extraction method ("llm:<model>@<prompt>"), if an AI made it. */
export function aiModel(c: Pick<Claim, "extraction_method">): string | null {
  return /^llm:([^@]+)@/.exec(c.extraction_method ?? "")?.[1] ?? null;
}

/** A claim an AI model read out of a published paper (as opposed to a database record or an AI hypothesis). */
export const foundByAi = (c: Pick<Claim, "source_type" | "extraction_method">) =>
  c.source_type === "published" && aiModel(c) !== null;

export const isHypothesis = (c: Pick<Claim, "source_type" | "status" | "predicate">) =>
  c.source_type === "ai_generated" ||
  c.status === "inference" ||
  HYPOTHESIS_PREDICATES.has(c.predicate);

export type ClaimKind =
  "conflict" | "hypothesis" | "reviewed" | "literature" | "database" | "synthetic";

export function claimKind(c: Claim): ClaimKind {
  if (c.contradicts.length > 0) return "conflict";
  if (isHypothesis(c)) return "hypothesis";
  if (c.review_state === "reviewed") return "reviewed";
  if (c.source_type === "synthetic_fixture") return "synthetic";
  if (c.source_type === "published") return "literature";
  return "database";
}

export const KIND_LABEL: Record<ClaimKind, string> = {
  conflict: "Conflicting evidence",
  hypothesis: "Hypothesis",
  reviewed: "Reviewed",
  literature: "From a published paper",
  database: "Database record",
  synthetic: "Synthetic demo data",
};

/** Short origin line shown on every claim, so the origin is visible without opening anything. */
export function originLabel(c: Claim): string {
  if (c.source_type === "ai_generated") return "AI hypothesis, not a finding";
  if (isDrugClaim(c)) return "Treatment idea: hypothesis only, not a recommendation";
  if (foundByAi(c)) return "Found by AI in this article";
  if (c.source_type === "published") return "Published paper";
  if (c.source_type === "database_record") return "Public database record";
  if (c.source_type === "lab_reported") return "Lab-reported, not peer reviewed";
  return "Synthetic demo data";
}

/** What a reader should take from a claim, before any detail. */
export function meaning(c: Claim): string[] {
  const out: string[] = [
    {
      database_record: "Copied from a public reference database; the record is quoted below.",
      published: "Quoted from a published paper.",
      lab_reported: "Reported by a lab; not peer reviewed.",
      synthetic_fixture: "Made-up demo data. Not a real finding.",
      ai_generated:
        "A hypothesis written by an AI model, not found in any source. It never counts as evidence.",
    }[c.source_type],
  ];
  if (foundByAi(c))
    out.push(
      "Found by AI in this article and checked word for word against it; not reviewed by a human.",
    );
  if (c.predicate === "GENE_ASSOCIATED_WITH_DISEASE")
    out.push(
      "A link between a gene and a disease is an association; on its own it does not show the gene causes it.",
    );
  if (c.status === "computational_prediction")
    out.push("This is a computer prediction, not an observation.");
  if (c.status === "inference") out.push("This is an inference, not something directly observed.");
  if (HYPOTHESIS_PREDICATES.has(c.predicate))
    out.push("Recorded as a hypothesis only, never as a finding.");
  if (isDrugClaim(c))
    out.push(
      "A treatment idea to discuss with experts. It is not advice, dosing or a recommendation to treat anyone.",
    );
  out.push(
    c.review_state === "reviewed"
      ? "Reviewed by an expert."
      : c.review_state === "disputed"
        ? "Disputed: a reviewer disagrees."
        : "Not reviewed by an expert.",
  );
  return out;
}

export const CATEGORY_CLASS: Record<EvidenceCategory, string> = {
  "reviewed mechanistic lead": "evidence-reviewed",
  "literature-supported lead": "evidence-literature",
  "symptom-level lead": "evidence-symptom",
  "hypothesis only": "evidence-hypothesis",
  "conflicting evidence": "evidence-conflict",
  "insufficient coverage": "evidence-gap",
};

export const CATEGORY_HELP: Record<EvidenceCategory, string> = {
  "reviewed mechanistic lead": "A reviewer has checked the mechanism evidence behind this link.",
  "literature-supported lead": "Published papers report a shared feature. Nobody has reviewed it.",
  "symptom-level lead": "The two share recorded symptoms. This is similarity, not a shared cause.",
  "hypothesis only": "Only a hypothesis supports this link; it is not evidence.",
  "conflicting evidence": "Two sources report opposite effects. Both are shown.",
  "insufficient coverage":
    "Too little is indexed to say anything either way. Missing is not the same as none.",
};

export const GAP_KIND: Record<string, string> = {
  insufficient_coverage: "Insufficient coverage",
  unresolved_identity: "Unresolved identity",
  hypothesis_only: "Hypothesis only",
  conflicting_evidence: "Conflicting evidence",
  no_supported_route: "No supported route",
  not_yet_researched: "Not yet researched",
};

export const CHANNEL_NAME: Record<string, string> = {
  phenotype: "Symptoms",
  dna: "DNA",
  rna: "RNA",
  mechanism: "Mechanism",
  dna_variants: "Shared gene",
  rna_effects: "RNA",
  molecular_mechanisms: "Mechanism",
  experimental_findings: "Experiments",
};

export const clean = (label: string) => label.replace(/\s*\(synthetic\)/i, "");

export const doiOf = (url: string) => /(?:doi\.org\/|doi:)(10\.[^\s?#]+)/i.exec(url)?.[1];

/**
 * Shared-feature text from the API reads like a log line ("directly links the two diseases: SHARES_PATHOGENIC_PATHWAY_WITH
 * (CLAIM:...)", "shared GO:0005764[CHEBI:16113]"). On screen the codes become plain words and the claim IDs are dropped,
 * because each claim is shown separately as a citation chip.
 */
export function humanize(text: string, name: (id: string) => string): string {
  return text
    .replace(/\bHP:\d+\s+(?=[A-Za-z])/g, "") // "HP:0000709 Psychosis" already carries its name
    .replace(/\s*\(CLAIM:[^)]*\)/g, "")
    .replace(
      /\b[A-Z]+(?:_[A-Z]+)+\b/g,
      (m) => PREDICATE_PLAIN[m] ?? m.toLowerCase().replaceAll("_", " "),
    )
    .replace(
      /\b((?:GO|CHEBI):\d+)\[((?:GO|CHEBI):\d+)\]/g,
      (_, a: string, b: string) => `${name(a)} (${name(b)})`,
    )
    .replace(/\b(?:HGNC|MONDO|HP|GO|CHEBI):\d+/g, (id) => name(id))
    .replace(/^shared /, "");
}
