// Closed-loop experiment helpers: plain labels, plate-reader CSV parsing, and the planned robot moves as replay steps.
import type { ExpMetric, ExpPlan } from "@/lib/api";
import type { WorkflowStep } from "@/lib/simulation";

export const METRIC: Record<ExpMetric, { label: string; unit: string; help: string }> = {
  z_prime: {
    label: "Z′ (plate quality)",
    unit: "",
    help: "1 − 3(SD vehicle + SD positive) / |mean vehicle − mean positive|",
  },
  signal_to_background: {
    label: "Signal / background",
    unit: "×",
    help: "mean vehicle ÷ mean positive control",
  },
  cv_vehicle_pct: { label: "CV of vehicle controls", unit: "%", help: "SD ÷ mean × 100" },
  cv_positive_pct: { label: "CV of positive controls", unit: "%", help: "SD ÷ mean × 100" },
  fit_r2: { label: "Curve fit R²", unit: "", help: "4-parameter logistic fit to % activity" },
  points_low_plateau: {
    label: "Points on the flat top",
    unit: "points",
    help: "concentrations at or below the lower bend (IC50 ÷ 4.68^(1/Hill))",
  },
  points_high_plateau: {
    label: "Points on the flat bottom",
    unit: "points",
    help: "concentrations at or above the upper bend (IC50 × 4.68^(1/Hill))",
  },
  ic50_inside_range: { label: "IC50 inside the tested range", unit: "1 = yes", help: "" },
};

export const PLAN_CHECK: Record<string, string> = {
  plate_capacity: "Layout fits the plate",
  pipette_range: "Pipette volume range",
  stock_limit: "Stock is strong enough",
  dmso_limit: "DMSO limit",
  well_volume: "Well volume",
  tips: "Tips available",
  motion: "Robot motion (MuJoCo)",
};

export const VERDICT: Record<string, { text: string; cls: string }> = {
  pass: { text: "Passed your criteria", cls: "text-reviewed border-reviewed" },
  technical_fail: {
    text: "Plate failed quality control",
    cls: "text-destructive border-destructive",
  },
  assay_fail: { text: "Curve failed your criteria", cls: "text-conflict border-conflict" },
  plan_fail: { text: "The robot cannot run this plan", cls: "text-destructive border-destructive" },
};

export const STATUS: Record<string, string> = {
  continue: "Next run queued",
  done: "Done: confirmed",
  stopped: "Stopped by your rules",
  needs_researcher: "Needs you: no allowed change fits",
};

/** "A1,1234" lines (or tab/semicolon separated; a header row is skipped). Returns readings and the lines refused. */
export function parseReadings(text: string): { readings: Record<string, number>; bad: string[] } {
  const readings: Record<string, number> = {};
  const bad: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const [w, v] = line.split(/[,;\t]/).map((x) => x.trim());
    const well = (w ?? "").toUpperCase().replace(/^([A-H])0(\d)$/, "$1$2");
    const value = Number(v);
    if (/^[A-H](?:[1-9]|1[0-2])$/.test(well) && v !== "" && Number.isFinite(value))
      readings[well] = value;
    else if (!/well/i.test(line)) bad.push(line);
  }
  return { readings, bad };
}

const TIPRACK: [number, number, number] = [40, 40, 15];
const SOURCE: [number, number, number] = [40, 150, 10];
const WASTE: [number, number, number] = [40, 100, 30];

/** The scene's coordinates for a planned operation (robotics/fixtures/valid_transfer.json: A1 at 150, 60 mm; 9 mm pitch). */
export function planToSteps(plan: ExpPlan): WorkflowStep[] {
  return plan.ops.map((o, i) => {
    let end = TIPRACK;
    if (o.op === "aspirate") end = SOURCE;
    if (o.op === "drop_tip") end = WASTE;
    if (o.op === "dispense" && o.well) {
      const row = o.well.charCodeAt(0) - 65;
      const col = Number(o.well.slice(1));
      end = [150 + (col - 1) * 9, 60 + row * 9, 25];
    }
    const title = {
      pick_tip: "Pick up tip",
      aspirate: "Aspirate the dilution",
      dispense: "Dispense to well",
      drop_tip: "Drop tip",
    }[o.op];
    return {
      id: i + 1,
      title,
      action: `${o.op}${o.well ? ` ${o.well}` : ""}${o.volume_ul ? ` · ${o.volume_ul} µL` : ""}`,
      duration: "",
      wells: o.well ? [o.well] : [],
      op: o.op,
      endMm: end,
      failed: false,
    };
  });
}

export const fmt = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined
    ? "—"
    : Math.abs(v) >= 1000
      ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : Number(v.toPrecision(Math.max(digits, 1))).toString();
