import { describe, expect, it } from "vitest";
import type { SimRun } from "@/lib/api";
import { runToSteps, wellAt } from "@/lib/simulation";

const run = (trace: SimRun["report"]["operation_trace"]) =>
  ({ report: { operation_trace: trace } }) as unknown as SimRun;

describe("simulation replay steps", () => {
  it("maps dispense coordinates to wells (A1 at 150, 60 mm; 9 mm pitch) and rejects off-plate points", () => {
    expect(wellAt([150, 60, 25])).toBe("A1");
    expect(wellAt([159, 69, 25])).toBe("B2");
    expect(wellAt([40, 40, 15])).toBeNull();
  });

  it("keeps a failed operation visible as failed and fills no well for it", () => {
    const steps = runToSteps(
      run([{ op_index: 0, op: "dispense", status: "blocked", end_mm: [150, 60, 25] }]),
    );
    expect(steps[0]).toMatchObject({ failed: true, wells: [], op: "dispense" });
    expect(steps[0]?.action).toContain("(blocked)");
  });

  it("falls back to one initialise step for an empty trace instead of crashing", () => {
    expect(runToSteps(run([]))).toHaveLength(1);
  });
});
