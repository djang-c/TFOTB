/**
 * The 10× case as arithmetic. Every input is a number the reader can change, and each one is tagged with where it comes
 * from. Nothing here is a measurement of a real lab: the point is to show which assumptions a 10× claim depends on.
 *
 * Milestone: from a candidate connection to a decision-ready first result, in working days.
 *   A. an evidence brief: the supported connection, its sources and what is unknown
 *   B. a quality-checked dose-response for the lead: the experiment is defined, run until it passes, and reviewed
 */

export type TenxInputs = {
  /** A. working days for a person to build a sourced brief by hand */
  manualBriefDays: number;
  /** A. working hours for a person to check the sources of a brief the site assembled */
  verifyHours: number;
  /** B. working days to define the experiment (parameters, limits, criteria, rules). The same either way. */
  defineDays: number;
  /** B. runs needed before every pass criterion is met. The overnight loop on this site gives this number. */
  runsNeeded: number;
  /** B. working days between two manual runs: plan, book the robot, run, read, analyse, decide the change */
  manualTurnaroundDays: number;
  /** B. hours one run occupies the robot (dispensing, incubation, reading) */
  runHours: number;
  /** B. hours of the night the robot may run unattended */
  nightHours: number;
  /** B. working days for a person to review the finished result. The same either way. */
  reviewDays: number;
};

export type TenxResult = {
  manualDays: number;
  assistedDays: number;
  speedup: number;
  nights: number;
  runsPerNight: number;
  /** The days automation cannot remove: defining, checking sources, reviewing. */
  fixedDays: number;
  /** The largest speedup possible if the loop itself took no time */
  ceiling: number;
};

export const DEFAULTS: TenxInputs = {
  manualBriefDays: 5,
  verifyHours: 4,
  defineDays: 1,
  runsNeeded: 4,
  manualTurnaroundDays: 3,
  runHours: 2,
  nightHours: 12,
  reviewDays: 0.5,
};

const HOURS_PER_DAY = 8;
const pos = (x: number) => (Number.isFinite(x) && x > 0 ? x : 0);

export function compare(i: TenxInputs): TenxResult {
  const runs = Math.max(1, Math.round(pos(i.runsNeeded)));
  const runsPerNight = Math.max(1, Math.floor(pos(i.nightHours) / Math.max(pos(i.runHours), 0.01)));
  const nights = Math.ceil(runs / runsPerNight);
  const verifyDays = pos(i.verifyHours) / HOURS_PER_DAY;
  const fixedDays = verifyDays + pos(i.defineDays) + pos(i.reviewDays);
  const manualDays =
    pos(i.manualBriefDays) +
    pos(i.defineDays) +
    runs * pos(i.manualTurnaroundDays) +
    pos(i.reviewDays);
  const assistedDays = fixedDays + nights;
  return {
    manualDays,
    assistedDays,
    speedup: assistedDays > 0 ? manualDays / assistedDays : 0,
    nights,
    runsPerNight,
    fixedDays,
    ceiling: fixedDays > 0 ? manualDays / fixedDays : 0,
  };
}

/**
 * The manual turnaround (working days between runs) at which the speedup reaches `target`, with everything else held.
 * null when it is already met with no turnaround at all.
 */
export function breakEvenTurnaround(i: TenxInputs, target = 10): number | null {
  const r = compare(i);
  const runs = Math.max(1, Math.round(pos(i.runsNeeded)));
  const rest = pos(i.manualBriefDays) + pos(i.defineDays) + pos(i.reviewDays);
  const t = (target * r.assistedDays - rest) / runs;
  return t > 0 ? t : null;
}

export type Scenario = { key: string; label: string; note: string; inputs: Partial<TenxInputs> };

/** Starting points, not findings. Each says what kind of lab it stands for. */
export const SCENARIOS: Scenario[] = [
  {
    key: "inhouse",
    label: "Own lab, robot on the bench",
    note: "A run can start the day after the last one was read.",
    inputs: { manualTurnaroundDays: 2 },
  },
  {
    key: "base",
    label: "Typical academic lab",
    note: "One run, then a day to analyse and decide, then a day to set up.",
    inputs: { manualTurnaroundDays: 3 },
  },
  {
    key: "core",
    label: "Shared core facility",
    note: "The robot is booked in slots, so each change waits for the next one.",
    inputs: { manualTurnaroundDays: 7 },
  },
];

export const fmtDays = (d: number) => `${d >= 10 ? d.toFixed(0) : d.toFixed(1)} days`;
export const fmtX = (x: number) => `${x >= 10 ? x.toFixed(0) : x.toFixed(1)}×`;
