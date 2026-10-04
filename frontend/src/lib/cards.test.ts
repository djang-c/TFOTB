import { describe, expect, it } from "vitest";
import type { ActionCard } from "@/lib/api";
import { cardToMarkdown, footnoteOrder } from "@/lib/cards";

const card = {
  card_id: "CARD:1",
  kind: "evidence_brief",
  audience: "science",
  this_week: "Read the paper.",
  responsible_human: "A reviewer",
  body_markdown: "# T\nOne [^c:CLAIM:a] and two [^c:CLAIM:b] and again [^c:CLAIM:a].",
  claim_ids: [],
  contact: null,
  reuse_limits: [],
  limitations: ["Unreviewed."],
  generated_by: "template",
} as ActionCard;

describe("action cards", () => {
  it("numbers footnotes in order of first use", () => {
    expect(footnoteOrder(card.body_markdown)).toEqual(["CLAIM:a", "CLAIM:b"]);
  });
  it("exports Markdown whose numbered sources and limitations travel with the text", () => {
    const md = cardToMarkdown(card);
    expect(md).toContain("One [1] and two [2] and again [1].");
    expect(md).toContain("[2] CLAIM:b");
    expect(md).toContain("- Unreviewed.");
    expect(md).toContain("not a clinical recommendation");
  });
});
