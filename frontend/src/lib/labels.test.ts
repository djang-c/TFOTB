import { describe, expect, it } from "vitest";
import { claim } from "@/test/fixtures";
import {
  aiModel,
  claimKind,
  foundByAi,
  humanize,
  isDrugClaim,
  isHypothesis,
  meaning,
  originLabel,
} from "@/lib/labels";

describe("origin labels", () => {
  it("names the model that extracted a claim, and only for AI-extracted published claims", () => {
    expect(aiModel(claim())).toBe("some-model");
    expect(aiModel(claim({ extraction_method: "structured_field" }))).toBeNull();
    expect(
      foundByAi(claim({ predicate: "ACCUMULATES_IN_COMPARTMENT", status: "reported_observation" })),
    ).toBe(true);
    expect(foundByAi(claim({ source_type: "database_record" }))).toBe(false);
  });

  it("never presents an AI hypothesis as a finding", () => {
    const h = claim({ source_type: "ai_generated", predicate: "SHARES_PATHOGENIC_PATHWAY_WITH" });
    expect(originLabel(h)).toBe("AI hypothesis, not a finding");
    expect(isHypothesis(h)).toBe(true);
    expect(meaning(h).join(" ")).toMatch(/never counts as evidence/);
  });

  it("shows a drug as a treatment idea, hypothesis only, and says it is not advice", () => {
    const d = claim();
    expect(isDrugClaim(d)).toBe(true);
    expect(originLabel(d)).toBe("Treatment idea: hypothesis only, not a recommendation");
    expect(claimKind(d)).toBe("hypothesis");
    expect(meaning(d).join(" ")).toMatch(/not advice, dosing or a recommendation/);
  });

  it("says an AI found an ordinary published observation, and that no human reviewed it", () => {
    const c = claim({ predicate: "ACCUMULATES_IN_COMPARTMENT", status: "reported_observation" });
    expect(originLabel(c)).toBe("Found by AI in this article");
    expect(claimKind(c)).toBe("literature");
    expect(meaning(c)).toContain("Not reviewed by an expert.");
  });

  it("marks a claim that others contradict as conflicting evidence", () => {
    expect(
      claimKind(
        claim({
          predicate: "ACCUMULATES_IN_COMPARTMENT",
          status: "reported_observation",
          contradicts: ["CLAIM:x"],
        }),
      ),
    ).toBe("conflict");
  });

  it("labels demo data as demo data", () => {
    expect(
      originLabel(
        claim({
          source_type: "synthetic_fixture",
          predicate: "ASSOCIATED_WITH_PHENOTYPE",
          status: "reported_observation",
        }),
      ),
    ).toBe("Synthetic demo data");
  });
});

describe("humanize shared-feature text", () => {
  const names: Record<string, string> = { "GO:0005764": "lysosome", "CHEBI:16113": "cholesterol" };
  const name = (id: string) => names[id] ?? id;

  it("turns codes into words and drops claim IDs (each claim is its own citation)", () => {
    expect(
      humanize(
        "directly links the two diseases: SHARES_PATHOGENIC_PATHWAY_WITH (CLAIM:PMID-1-abc)",
        name,
      ),
    ).toBe("directly links the two diseases: may share a disease process with");
    expect(humanize("shared GO:0005764[CHEBI:16113]", name)).toBe("lysosome (cholesterol)");
  });

  it("leaves an ID readable when nothing names it, and never invents a name", () => {
    expect(humanize("shared GO:0009999", name)).toBe("GO:0009999");
  });
});

describe("humanize symptom names", () => {
  it("does not repeat a name that the API already put after the HPO ID", () => {
    expect(humanize("HP:0000709 Psychosis", (id) => (id === "HP:0000709" ? "Psychosis" : id))).toBe(
      "Psychosis",
    );
  });
});
