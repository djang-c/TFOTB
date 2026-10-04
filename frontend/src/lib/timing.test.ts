import { describe, expect, it } from "vitest";
import { isTimingResults, summarize } from "./timing";

const ok = { manualPass: true, tfotbPass: true };

describe("timing study summary", () => {
  it("takes the median of the ratios and the median times, over pairs that both passed", () => {
    const r = summarize({
      participants: [
        { id: "P1", steps: { m1: { manualMin: 60, tfotbMin: 6, ...ok } } },
        { id: "P2", steps: { m1: { manualMin: 40, tfotbMin: 10, ...ok } } },
        { id: "P3", steps: { m1: { manualMin: 90, tfotbMin: 9, ...ok } } },
      ],
    });
    expect(r).toHaveLength(1);
    expect(r[0]).toMatchObject({
      step: "m1",
      n: 3,
      excluded: 0,
      medianManualMin: 60,
      medianTfotbMin: 9,
    });
    expect(r[0]!.medianRatio).toBeCloseTo(10, 6); // ratios 10, 4, 10
    expect(r[0]!.minRatio).toBeCloseTo(4, 6);
    expect(r[0]!.maxRatio).toBeCloseTo(10, 6);
  });

  it("reports a ratio under 10× as it is", () => {
    const r = summarize({
      participants: [{ id: "P1", steps: { m1: { manualMin: 30, tfotbMin: 10, ...ok } } }],
    });
    expect(r[0]!.medianRatio).toBeCloseTo(3, 6);
  });

  it("counts failed, unchecked and invalid runs as excluded instead of dropping them", () => {
    const r = summarize({
      participants: [
        {
          id: "P1",
          steps: { m2: { manualMin: 90, tfotbMin: 5, manualPass: false, tfotbPass: true } },
        },
        { id: "P2", steps: { m2: { manualMin: 50, tfotbMin: 5 } } },
        { id: "P3", steps: { m2: { manualMin: 0, tfotbMin: 5, ...ok } } },
        { id: "P4", steps: { m2: { manualMin: 50, tfotbMin: 5, ...ok } } },
      ],
    });
    expect(r[0]).toMatchObject({ n: 1, excluded: 3 });
  });

  it("gives n = 0 when nothing passed, without NaN", () => {
    const r = summarize({
      participants: [{ id: "P1", steps: { m3: { manualMin: 10, tfotbMin: 2 } } }],
    });
    expect(r[0]).toMatchObject({ n: 0, excluded: 1, medianRatio: 0 });
  });

  it("recognises the results file shape and rejects other things", () => {
    expect(isTimingResults({ participants: [{ id: "P1", steps: {} }] })).toBe(true);
    expect(isTimingResults({ participants: "no" })).toBe(false);
    expect(isTimingResults(null)).toBe(false);
    expect(isTimingResults("<html>")).toBe(false);
  });
});
