// Clusters around one searched disease, built from its related diseases: one cluster per shared thing.
import type { ReasonKind, RelatedDiseases, RelatedReason } from "@/lib/api";

export type Member = { id: string; label: string; reason: RelatedReason };
export type Cluster = {
  kind: ReasonKind;
  key: string;
  title: string;
  why: string;
  members: Member[];
};

/** How each kind of cluster is named and what its one shared thing means. */
const KIND: Record<ReasonKind, { title: (r: RelatedReason) => string; why: string }> = {
  gene: {
    title: (r) => `Linked to the gene ${r.label}`,
    why: "Each disease is linked to this gene in the HPO reference file. Same gene, not necessarily the same variant.",
  },
  mechanism: {
    title: (r) => `Same mechanism in papers: ${r.label}`,
    why: "Papers report this same process in each disease (for example, a substance building up in the same part of the cell).",
  },
  family: {
    title: (r) => `Forms of ${r.label}`,
    why: "The MONDO disease ontology files these diseases under the same parent disease.",
  },
  symptoms: {
    title: () => "Similar symptom pattern",
    why: "Their recorded symptom lists overlap strongly: similarity 0.4 or more on a 0 to 1 scale. Similar, not identical, and not a probability.",
  },
  paper_link: {
    title: () => "Proposed in papers (hypotheses)",
    why: "A paper suggests these diseases share a process. A suggestion, not a finding.",
  },
  ai_hypothesis: {
    title: () => "Proposed by AI (hypotheses)",
    why: "An AI read the stored paper claims and suggested a shared process. No paper states it; it is not a finding.",
  },
};
const ORDER: ReasonKind[] = [
  "gene",
  "mechanism",
  "family",
  "symptoms",
  "paper_link",
  "ai_hypothesis",
];

/** One cluster per shared thing: every related disease that shares that exact gene, mechanism, family or pattern. */
export function clustersOf(d: RelatedDiseases): Cluster[] {
  const out = new Map<string, Cluster>();
  for (const row of d.diseases)
    for (const r of row.reasons) {
      const one = r.kind === "symptoms" || r.kind === "paper_link" || r.kind === "ai_hypothesis";
      const key = `${r.kind}:${one ? "" : r.key}`;
      let c = out.get(key);
      if (!c) {
        c = { kind: r.kind, key, title: KIND[r.kind].title(r), why: KIND[r.kind].why, members: [] };
        out.set(key, c);
      }
      c.members.push({ id: row.id, label: row.label, reason: r });
    }
  return [...out.values()].sort(
    (a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind) || b.members.length - a.members.length,
  );
}
