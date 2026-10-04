import type { SimRun } from "@/lib/api";

export type WorkflowOp = "initialize" | "pick_tip" | "aspirate" | "dispense" | "mix" | "drop_tip";
export type WorkflowStep = {
  id: number;
  title: string;
  action: string;
  duration: string;
  wells: string[];
  op: WorkflowOp;
  endMm: [number, number, number];
  failed: boolean;
};

export const firstWorkflowStep: WorkflowStep = {
  id: 1,
  title: "Initialize deck",
  action: "Validate labware positions and tip inventory",
  duration: "00:00",
  wells: [],
  op: "initialize",
  endMm: [0, 0, 60],
  failed: false,
};

const TITLES: Record<string, string> = {
  initialize: "Initialize deck",
  pick_tip: "Pick up tip",
  aspirate: "Aspirate from source",
  dispense: "Dispense to plate",
  mix: "Mix wells",
  drop_tip: "Drop tip",
};
const OPS: WorkflowOp[] = ["initialize", "pick_tip", "aspirate", "dispense", "mix", "drop_tip"];

/** Destination well label for a dispense coordinate (A1 at 150, 60 mm; 9 mm pitch). */
export function wellAt([x, y]: [number, number, number]): string | null {
  const col = Math.round((x - 150) / 9) + 1;
  const row = Math.round((y - 60) / 9);
  return col >= 1 && col <= 12 && row >= 0 && row < 8 ? `${"ABCDEFGH"[row]}${col}` : null;
}

/** The recorded operation trace as replay steps. Failed operations stay visible as failed; nothing is invented. */
export function runToSteps(run: SimRun): WorkflowStep[] {
  const trace = run.report.operation_trace;
  if (trace.length === 0) return [firstWorkflowStep];
  return trace.map((op, i) => {
    const well = op.op === "dispense" || op.op === "mix" ? wellAt(op.end_mm) : null;
    const failed = op.status !== "ok";
    return {
      id: i + 1,
      title: TITLES[op.op] ?? op.op,
      action: `${op.op} → ${op.end_mm.join(", ")} mm${failed ? ` (${op.status})` : ""}`,
      duration: `00:${String((i + 1) * 4).padStart(2, "0")}`,
      wells: !failed && well ? [well] : [],
      op: OPS.find((v) => v === op.op) ?? "initialize",
      endMm: op.end_mm,
      failed,
    };
  });
}
