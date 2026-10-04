import { describe, expect, it } from "vitest";
import { compareJourney, PERSONAS } from "./journey";

const maria = PERSONAS.find((p) => p.key === "maria")!;

describe("the 10× case on the brief's people", () => {
  it("covers Maria, Devon, Priya and Dr. Osei, each with a sentence from the brief", () => {
    expect(PERSONAS.map((p) => p.key)).toEqual(["maria", "devon", "priya", "osei"]);
    for (const p of PERSONAS) expect(p.pain.length).toBeGreaterThan(20);
  });

  it("adds Maria's steps: 30 working days by hand, 11 working hours with the product", () => {
    const r = compareJourney(maria);
    expect(r.manualDays).toBe(30);
    expect(r.assistedHours).toBe(11);
    expect(r.speedup).toBeCloseTo(240 / 11, 6);
  });

  it("says how much longer checking could take before 10× is lost", () => {
    const r = compareJourney(maria);
    const slower = compareJourney(maria, {
      m1: { assistedHours: 3 * r.headroom },
      m2: { assistedHours: 3 * r.headroom },
      m3: { assistedHours: 1 * r.headroom },
      m4: { assistedHours: 4 * r.headroom },
    });
    expect(slower.speedup).toBeCloseTo(10, 6);
  });

  it("shows what happens if checking takes three times as long", () => {
    const r = compareJourney(maria);
    expect(r.stressed).toBeCloseTo(r.speedup / 3, 6);
    expect(r.stressed).toBeLessThan(10);
  });

  it("uses an edited value, and ignores a blank or negative one", () => {
    expect(compareJourney(maria, { m1: { manualDays: 20 } }).manualDays).toBe(40);
    expect(compareJourney(maria, { m1: { manualDays: -5 } }).manualDays).toBe(30);
    expect(Number.isFinite(compareJourney(maria, { m1: { assistedHours: NaN } }).speedup)).toBe(
      true,
    );
  });

  it("marks what is not fully built", () => {
    expect(PERSONAS.filter((p) => p.built === "partial").map((p) => p.key)).toEqual([
      "priya",
      "osei",
    ]);
  });
});
