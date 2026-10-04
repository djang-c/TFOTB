import { describe, expect, it } from "vitest";
import type { RelatedDiseases, RelatedReason } from "@/lib/api";
import { clustersOf } from "@/lib/clusters";

const r = (kind: RelatedReason["kind"], key: string, label = key): RelatedReason => ({
  kind,
  key,
  label,
  evidence: kind === "symptoms" ? "similarity" : "reference",
  claim_ids: [],
  detail: "",
});
const data = (rows: [string, RelatedReason[]][]): RelatedDiseases => ({
  entity_id: "MONDO:1",
  applies: true,
  diseases: rows.map(([id, reasons]) => ({
    id,
    label: id,
    reasons,
    kinds: reasons.map((x) => x.kind),
    hierarchy: null,
  })),
  total: rows.length,
  counts: { gene: 0, mechanism: 0, paper_link: 0, family: 0, ai_hypothesis: 0, symptoms: 0 },
  none: rows.length === 0,
  note: "",
});

describe("clustersOf", () => {
  it("makes one cluster per shared thing; a disease can be in several", () => {
    const out = clustersOf(
      data([
        ["A", [r("gene", "HGNC:1", "CLN3"), r("symptoms", "phenotype")]],
        ["B", [r("gene", "HGNC:1", "CLN3")]],
        ["C", [r("gene", "HGNC:2", "NPC1"), r("symptoms", "phenotype")]],
      ]),
    );
    expect(out.map((c) => [c.title, c.members.map((m) => m.id)])).toEqual([
      ["Linked to the gene CLN3", ["A", "B"]],
      ["Linked to the gene NPC1", ["C"]],
      ["Similar symptom pattern", ["A", "C"]],
    ]);
  });
  it("has no clusters when nothing is related", () => {
    expect(clustersOf(data([]))).toEqual([]);
  });
});
