/** Summarises the timing study (docs/TIMING_STUDY.md). Only pairs where BOTH runs passed the quality bar enter the
 *  ratio; everything else is counted and reported, never dropped silently. */

export type StepTiming = {
  manualMin: number;
  tfotbMin: number;
  manualPass?: boolean;
  tfotbPass?: boolean;
};
export type Participant = { id: string; role?: string; steps: Record<string, StepTiming> };
export type TimingResults = { run_on?: string; participants: Participant[] };

export type StepSummary = {
  step: string;
  /** pairs where both runs passed and both times are positive */
  n: number;
  /** pairs reported but not counted: a failed or unchecked run, or a time that is not a positive number */
  excluded: number;
  medianManualMin: number;
  medianTfotbMin: number;
  medianRatio: number;
  minRatio: number;
  maxRatio: number;
};

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
};

export function isTimingResults(x: unknown): x is TimingResults {
  return (
    typeof x === "object" &&
    x !== null &&
    Array.isArray((x as TimingResults).participants) &&
    (x as TimingResults).participants.every(
      (p) => typeof p?.id === "string" && typeof p.steps === "object",
    )
  );
}

export function summarize(results: TimingResults): StepSummary[] {
  const byStep = new Map<string, StepTiming[]>();
  for (const p of results.participants)
    for (const [step, t] of Object.entries(p.steps))
      byStep.set(step, [...(byStep.get(step) ?? []), t]);
  const out: StepSummary[] = [];
  for (const [step, ts] of byStep) {
    const ok = ts.filter(
      (t) =>
        t.manualPass === true &&
        t.tfotbPass === true &&
        Number.isFinite(t.manualMin) &&
        Number.isFinite(t.tfotbMin) &&
        t.manualMin > 0 &&
        t.tfotbMin > 0,
    );
    if (!ok.length) {
      out.push({
        step,
        n: 0,
        excluded: ts.length,
        medianManualMin: 0,
        medianTfotbMin: 0,
        medianRatio: 0,
        minRatio: 0,
        maxRatio: 0,
      });
      continue;
    }
    const ratios = ok.map((t) => t.manualMin / t.tfotbMin);
    out.push({
      step,
      n: ok.length,
      excluded: ts.length - ok.length,
      medianManualMin: median(ok.map((t) => t.manualMin)),
      medianTfotbMin: median(ok.map((t) => t.tfotbMin)),
      medianRatio: median(ratios),
      minRatio: Math.min(...ratios),
      maxRatio: Math.max(...ratios),
    });
  }
  return out.sort((a, b) => a.step.localeCompare(b.step));
}
