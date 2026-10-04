import { describe, expect, it } from "vitest";
import type { ExpPlan } from "@/lib/api";
import { parseReadings, planToSteps } from "@/lib/experiment";

describe("parseReadings", () => {
  it("reads well,value lines in any common separator and skips the header", () => {
    const r = parseReadings("Well,Value\nB2,52310\nb03;48870\nC4\t1.5e4\n\nZ9,1\nB5,");
    expect(r.readings).toEqual({ B2: 52310, B3: 48870, C4: 15000 });
    expect(r.bad).toEqual(["Z9,1", "B5,"]);
  });
});

describe("planToSteps", () => {
  it("places each planned move at the scene's coordinates", () => {
    const plan = {
      ops: [
        { op: "pick_tip" },
        { op: "aspirate", volume_ul: 3 },
        { op: "dispense", well: "B3", volume_ul: 1 },
        { op: "drop_tip" },
      ],
    } as unknown as ExpPlan;
    const s = planToSteps(plan);
    expect(s.map((x) => x.endMm)).toEqual([
      [40, 40, 15],
      [40, 150, 10],
      [168, 69, 25],
      [40, 100, 30],
    ]);
    expect(s[2]!.wells).toEqual(["B3"]);
  });
});
