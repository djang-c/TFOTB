import { describe, expect, it } from "vitest";
import { breakEvenTurnaround, compare, DEFAULTS, SCENARIOS, type TenxInputs } from "./tenx";

const base: TenxInputs = DEFAULTS;

describe("10× case arithmetic", () => {
  it("adds up the manual and assisted routes from the stated inputs", () => {
    const r = compare(base);
    // manual: brief 5 + define 1 + 4 runs x 3 days + review 0.5
    expect(r.manualDays).toBeCloseTo(18.5, 6);
    // assisted: verify 4 h = 0.5 + define 1 + 1 night (6 runs fit in 12 h) + review 0.5
    expect(r.nights).toBe(1);
    expect(r.assistedDays).toBeCloseTo(3, 6);
    expect(r.speedup).toBeCloseTo(18.5 / 3, 6);
  });

  it("falls short of 10× on the default assumptions rather than claiming it", () => {
    expect(compare(base).speedup).toBeLessThan(10);
  });

  it("reaches 10× at the break-even turnaround and not below it", () => {
    const t = breakEvenTurnaround(base);
    expect(t).not.toBeNull();
    expect(compare({ ...base, manualTurnaroundDays: t! }).speedup).toBeCloseTo(10, 6);
    expect(compare({ ...base, manualTurnaroundDays: t! - 0.5 }).speedup).toBeLessThan(10);
  });

  it("needs more nights when the robot cannot fit every run in one night", () => {
    const r = compare({ ...base, runsNeeded: 13, runHours: 4, nightHours: 12 });
    expect(r.runsPerNight).toBe(3);
    expect(r.nights).toBe(5);
  });

  it("never exceeds the ceiling set by the work automation cannot remove", () => {
    const r = compare({ ...base, manualTurnaroundDays: 1000 });
    expect(r.ceiling).toBeGreaterThan(r.speedup);
    expect(r.fixedDays).toBeCloseTo(2, 6);
  });

  it("copes with empty, negative and non-numeric inputs without NaN", () => {
    const r = compare({
      ...base,
      runsNeeded: NaN,
      runHours: -3,
      nightHours: 0,
      reviewDays: -1,
      verifyHours: NaN,
    });
    for (const v of Object.values(r)) expect(Number.isFinite(v)).toBe(true);
  });

  it("orders the scenarios from fastest to slowest manual turnaround", () => {
    const speeds = SCENARIOS.map((s) => compare({ ...base, ...s.inputs }).speedup);
    expect([...speeds].sort((a, b) => a - b)).toEqual(speeds);
  });
});
