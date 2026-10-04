import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Moon, Pause, Play, Plus, RotateCcw, Trash2, Upload } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  api,
  type ExpCriterion,
  type ExpDefinition,
  type ExpMetric,
  type ExpPlan,
  type ExpRule,
  type ExpRun,
} from "@/lib/api";
import {
  fmt,
  METRIC,
  parseReadings,
  PLAN_CHECK,
  planToSteps,
  STATUS,
  VERDICT,
} from "@/lib/experiment";

const LabDeck3D = lazy(() =>
  import("@/components/LabDeck3D").then((m) => ({ default: m.LabDeck3D })),
);

export const Route = createFileRoute("/simulation")({
  ssr: false,
  head: () => ({ meta: [{ title: "Simulation — The Flight of the Buffalo" }] }),
  component: SimulationPage,
});

const STORE = "tfotb.experiment.v1";
type Saved = { definition: ExpDefinition; history: ExpRun[] };
function load(): Saved | null {
  try {
    const raw = window.localStorage.getItem(STORE);
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}
function save(s: Saved) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(s));
  } catch {
    /* storage blocked: the experiment still works in this tab */
  }
}

const TABS = [
  ["define", "1 · Define the experiment"],
  ["plan", "2 · Robot plan"],
  ["run", "3 · Run and evaluate"],
  ["log", "4 · Overnight log"],
] as const;
type Tab = (typeof TABS)[number][0];

function SimulationPage() {
  const example = useQuery({ queryKey: ["experiment-example"], queryFn: api.experimentExample });
  const [def, setDef] = useState<ExpDefinition | null>(null);
  const [history, setHistory] = useState<ExpRun[]>([]);
  const [tab, setTab] = useState<Tab>("define");
  useEffect(() => {
    if (def || !example.data) return;
    const s = load();
    setDef(s?.definition ?? example.data.definition);
    setHistory(s?.history ?? []);
  }, [def, example.data]);
  useEffect(() => {
    if (def) save({ definition: def, history });
  }, [def, history]);

  if (example.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The experiment service could not be reached. Check that the API is running.
      </p>
    );
  if (!def) return <p className="p-10 text-center text-sm text-muted-foreground">Loading…</p>;
  const reset = () => {
    if (example.data) setDef(example.data.definition);
    setHistory([]);
  };
  return (
    <div className="px-5 py-8 lg:px-10">
      <header className="flex flex-col gap-4 border-b border-border pb-6 xl:flex-row xl:items-end">
        <div className="max-w-4xl">
          <p className="section-kicker">Simulation · overnight experiments</p>
          <h1 className="mt-2 text-3xl font-semibold">{def.title}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            You define the experiment: what may change between runs and within which limits, what
            result you expect, and what to change if a run fails. The robot plan is checked against
            your real volumes, concentrations, tips and the robot&apos;s reach. After each run the
            results are scored against your criteria and the next run changes only what your rules
            allow.
          </p>
        </div>
        <div className="flex gap-2 xl:ml-auto">
          <Button variant="outline" size="sm" onClick={reset}>
            <RotateCcw /> Start again from the example
          </Button>
        </div>
      </header>

      <nav aria-label="Experiment steps" className="mt-5 flex flex-wrap gap-1.5">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={tab === k}
            onClick={() => setTab(k)}
            className={`rounded-md border px-3 py-1.5 text-sm ${tab === k ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary/50"}`}
          >
            {label}
            {k === "log" && history.length > 0 ? ` (${history.length})` : ""}
          </button>
        ))}
      </nav>

      <div className="mt-6">
        {tab === "define" && <Define def={def} setDef={setDef} />}
        {tab === "plan" && <PlanView def={def} values={history.at(-1)?.next_values} />}
        {tab === "run" && (
          <RunView
            def={def}
            history={history}
            setHistory={setHistory}
            onLog={() => setTab("log")}
          />
        )}
        {tab === "log" && <Log history={history} def={def} />}
      </div>

      <p className="mt-8 border-t border-border pt-4 text-[11px] leading-5 text-muted-foreground">
        What is real: your definition, the volume and concentration arithmetic, the pipette, tip and
        DMSO limits, and the robot&apos;s motion check (MuJoCo). What is not: liquids, calibration
        and biology are not simulated. Readings are either yours (MEASURED, from your plate reader)
        or SYNTHETIC (made by a stated model to show the loop; never evidence about any compound).
        The default criteria come from the NIH Assay Guidance Manual, Zhang 1999 (Z′) and Sebaugh
        2011 (curve plateaus); the default rules are a starting design, not a published standard.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- 1. define */

function Panel({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <section className="min-w-0 rounded-lg border border-border bg-card p-5">
      <h2 className="text-sm font-semibold">{title}</h2>
      {note && <p className="mt-1 text-xs leading-5 text-muted-foreground">{note}</p>}
      <div className="mt-3 overflow-x-auto">{children}</div>
    </section>
  );
}

const input =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs focus:border-primary focus:outline-none";
const num = (v: string) => (v.trim() === "" ? NaN : Number(v));

function Define({ def, setDef }: { def: ExpDefinition; setDef: (d: ExpDefinition) => void }) {
  const set = <K extends keyof ExpDefinition>(k: K, v: ExpDefinition[K]) =>
    setDef({ ...def, [k]: v });
  const varied = def.parameters.filter((p) => p.role === "varied");
  const whens = [
    ...def.criteria.map((c) => [c.id, `fails: ${c.id}`] as const),
    ...Object.entries(PLAN_CHECK)
      .filter(([k]) => k !== "motion")
      .map(([k, l]) => [k, `plan check fails: ${l}`] as const),
  ];
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="The question">
          <label className="block text-xs text-muted-foreground">
            Title
            <input
              className={`${input} mt-1`}
              value={def.title}
              onChange={(e) => set("title", e.target.value)}
            />
          </label>
          <label className="mt-3 block text-xs text-muted-foreground">
            Hypothesis
            <textarea
              className={`${input} mt-1 h-16 py-1`}
              value={def.hypothesis}
              onChange={(e) => set("hypothesis", e.target.value)}
            />
          </label>
          <label className="mt-3 block text-xs text-muted-foreground">
            What result do you expect?
            <textarea
              className={`${input} mt-1 h-16 py-1`}
              value={def.expected}
              onChange={(e) => set("expected", e.target.value)}
            />
          </label>
        </Panel>
        <Panel
          title="Instrument and plate"
          note="Your robot's real limits. A plan outside them is refused, never adjusted to fit."
        >
          <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-3">
            <label>
              Pipette
              <input
                className={`${input} mt-1`}
                value={def.instrument.pipette}
                onChange={(e) => set("instrument", { ...def.instrument, pipette: e.target.value })}
              />
            </label>
            {(
              [
                ["pipette_min_ul", "Pipette min (µL)"],
                ["pipette_max_ul", "Pipette max (µL)"],
                ["tips_available", "Tips available"],
                ["well_max_ul", "Well capacity (µL)"],
              ] as const
            ).map(([k, l]) => (
              <label key={k}>
                {l}
                <input
                  type="number"
                  className={`${input} mt-1`}
                  value={def.instrument[k]}
                  onChange={(e) =>
                    set("instrument", { ...def.instrument, [k]: num(e.target.value) })
                  }
                />
              </label>
            ))}
            <label>
              Readout
              <select
                className={`${input} mt-1`}
                value={def.readout}
                onChange={(e) => set("readout", e.target.value as ExpDefinition["readout"])}
              >
                <option value="luminescence">luminescence</option>
                <option value="fluorescence">fluorescence</option>
                <option value="absorbance">absorbance</option>
              </select>
            </label>
            <label>
              Outer wells
              <select
                className={`${input} mt-1`}
                value={def.edge_policy}
                onChange={(e) => set("edge_policy", e.target.value as ExpDefinition["edge_policy"])}
              >
                <option value="buffer_outer_wells">buffer only (edge effect)</option>
                <option value="use_all_wells">use all wells</option>
              </select>
            </label>
            <label>
              Controls of each type
              <input
                type="number"
                className={`${input} mt-1`}
                value={def.controls_per_type}
                onChange={(e) => set("controls_per_type", num(e.target.value))}
              />
            </label>
          </div>
        </Panel>
      </div>

      <Panel
        title="Parameters"
        note="Varied parameters may change between runs, only within their range and by at most the fold-change you allow per run. Fixed parameters never change."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-1.5 font-normal">Parameter</th>
                <th className="font-normal">Unit</th>
                <th className="font-normal">Role</th>
                <th className="font-normal">Start value</th>
                <th className="font-normal">Min</th>
                <th className="font-normal">Max</th>
                <th className="font-normal">Max change per run (×)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {def.parameters.map((p, i) => {
                const up = (patch: Partial<typeof p>) =>
                  set(
                    "parameters",
                    def.parameters.map((x, j) => (j === i ? { ...x, ...patch } : x)),
                  );
                return (
                  <tr key={p.name}>
                    <td className="py-1.5 pr-2 font-medium">{p.label}</td>
                    <td className="pr-2 text-muted-foreground">{p.unit}</td>
                    <td className="pr-2">
                      <select
                        className={input}
                        value={p.role}
                        onChange={(e) => up({ role: e.target.value as typeof p.role })}
                      >
                        <option value="varied">may change</option>
                        <option value="fixed">fixed</option>
                      </select>
                    </td>
                    {(["value", "min", "max"] as const).map((k) => (
                      <td key={k} className="pr-2">
                        <input
                          type="number"
                          className={input}
                          value={p[k]}
                          onChange={(e) => up({ [k]: num(e.target.value) })}
                        />
                      </td>
                    ))}
                    <td>
                      <input
                        type="number"
                        className={input}
                        value={p.max_change_factor ?? ""}
                        placeholder="no limit"
                        disabled={p.role === "fixed"}
                        onChange={(e) =>
                          up({ max_change_factor: e.target.value ? num(e.target.value) : null })
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          title="Pass criteria (what result you expect)"
          note="Technical criteria judge the plate; assay criteria judge the curve. A run passes only if all pass."
        >
          <ul className="space-y-2">
            {def.criteria.map((c, i) => (
              <CriterionRow
                key={i}
                c={c}
                onChange={(next) =>
                  set(
                    "criteria",
                    def.criteria.map((x, j) => (j === i ? next : x)),
                  )
                }
                onRemove={() =>
                  set(
                    "criteria",
                    def.criteria.filter((_, j) => j !== i),
                  )
                }
              />
            ))}
          </ul>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() =>
              set("criteria", [
                ...def.criteria,
                {
                  id: `criterion_${def.criteria.length + 1}`,
                  metric: "signal_to_background",
                  op: ">=",
                  threshold: 3,
                  severity: "technical",
                  why: "",
                },
              ])
            }
          >
            <Plus /> Add a criterion
          </Button>
        </Panel>
        <Panel
          title="If a run fails, what to change"
          note="Rules are tried in this order; at most one change per parameter per run. A change that leaves your range is refused and shown."
        >
          <ul className="space-y-2">
            {def.rules.map((r, i) => (
              <RuleRow
                key={i}
                r={r}
                whens={whens}
                params={varied.map((p) => [p.name, p.label] as const)}
                onChange={(next) =>
                  set(
                    "rules",
                    def.rules.map((x, j) => (j === i ? next : x)),
                  )
                }
                onRemove={() =>
                  set(
                    "rules",
                    def.rules.filter((_, j) => j !== i),
                  )
                }
              />
            ))}
          </ul>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() =>
              set("rules", [
                ...def.rules,
                {
                  id: `rule_${def.rules.length + 1}`,
                  when: def.criteria[0]?.id ?? "dmso_limit",
                  action: "rerun",
                  parameter: null,
                  operation: null,
                  amount: null,
                  max_uses: 1,
                  why: "",
                },
              ])
            }
          >
            <Plus /> Add a rule
          </Button>
          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs text-muted-foreground">
            <label>
              Passing runs in a row needed (same settings)
              <input
                type="number"
                className={`${input} mt-1`}
                value={def.passes_needed}
                onChange={(e) => set("passes_needed", num(e.target.value))}
              />
            </label>
            <label>
              Most runs overnight
              <input
                type="number"
                className={`${input} mt-1`}
                value={def.max_runs}
                onChange={(e) => set("max_runs", num(e.target.value))}
              />
            </label>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function CriterionRow({
  c,
  onChange,
  onRemove,
}: {
  c: ExpCriterion;
  onChange: (c: ExpCriterion) => void;
  onRemove: () => void;
}) {
  return (
    <li className="rounded-md border border-border p-2.5">
      <div className="grid grid-cols-[minmax(0,1.4fr)_4rem_5rem_6.5rem_auto] items-center gap-2">
        <select
          className={input}
          value={c.metric}
          aria-label="Metric"
          onChange={(e) => onChange({ ...c, metric: e.target.value as ExpMetric })}
        >
          {Object.entries(METRIC).map(([k, m]) => (
            <option key={k} value={k}>
              {m.label}
            </option>
          ))}
        </select>
        <select
          className={input}
          value={c.op}
          aria-label="Comparison"
          onChange={(e) => onChange({ ...c, op: e.target.value as ExpCriterion["op"] })}
        >
          <option value=">=">≥</option>
          <option value="<=">≤</option>
        </select>
        <input
          type="number"
          className={input}
          aria-label="Threshold"
          value={c.threshold}
          onChange={(e) => onChange({ ...c, threshold: num(e.target.value) })}
        />
        <select
          className={input}
          value={c.severity}
          aria-label="Kind"
          onChange={(e) => onChange({ ...c, severity: e.target.value as ExpCriterion["severity"] })}
        >
          <option value="technical">plate (technical)</option>
          <option value="assay">curve (assay)</option>
        </select>
        <Button variant="ghost" size="icon" aria-label={`Remove ${c.id}`} onClick={onRemove}>
          <Trash2 />
        </Button>
      </div>
      <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
        <code>{c.id}</code>
        {c.why ? ` · ${c.why}` : ""}
      </p>
    </li>
  );
}

function RuleRow({
  r,
  whens,
  params,
  onChange,
  onRemove,
}: {
  r: ExpRule;
  whens: (readonly [string, string])[];
  params: (readonly [string, string])[];
  onChange: (r: ExpRule) => void;
  onRemove: () => void;
}) {
  return (
    <li className="rounded-md border border-border p-2.5">
      <div className="grid grid-cols-2 items-center gap-2 sm:grid-cols-[minmax(0,1.3fr)_6rem_minmax(0,1fr)_5.5rem_4.5rem_auto]">
        <select
          className={input}
          aria-label="When"
          value={r.when}
          onChange={(e) => onChange({ ...r, when: e.target.value })}
        >
          {whens.map(([k, l]) => (
            <option key={k} value={k}>
              {l}
            </option>
          ))}
        </select>
        <select
          className={input}
          aria-label="Action"
          value={r.action}
          onChange={(e) => {
            const action = e.target.value as ExpRule["action"];
            onChange(
              action === "change"
                ? {
                    ...r,
                    action,
                    parameter: r.parameter ?? params[0]?.[0] ?? null,
                    operation: r.operation ?? "multiply",
                    amount: r.amount ?? 2,
                  }
                : { ...r, action, parameter: null, operation: null, amount: null },
            );
          }}
        >
          <option value="change">change</option>
          <option value="rerun">repeat</option>
          <option value="stop">stop</option>
        </select>
        {r.action === "change" ? (
          <>
            <select
              className={input}
              aria-label="Parameter"
              value={r.parameter ?? ""}
              onChange={(e) => onChange({ ...r, parameter: e.target.value })}
            >
              {params.map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
            <select
              className={input}
              aria-label="Operation"
              value={r.operation ?? "multiply"}
              onChange={(e) =>
                onChange({ ...r, operation: e.target.value as NonNullable<ExpRule["operation"]> })
              }
            >
              <option value="multiply">× by</option>
              <option value="add">+ add</option>
              <option value="set">= set to</option>
            </select>
            <input
              type="number"
              className={input}
              aria-label="Amount"
              value={r.amount ?? ""}
              onChange={(e) => onChange({ ...r, amount: num(e.target.value) })}
            />
          </>
        ) : (
          <span className="col-span-1 text-[11px] text-muted-foreground sm:col-span-3">
            {r.action === "rerun" ? "repeat with the same settings" : "stop the overnight run"}
          </span>
        )}
        <Button variant="ghost" size="icon" aria-label={`Remove ${r.id}`} onClick={onRemove}>
          <Trash2 />
        </Button>
      </div>
      <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
        <code>{r.id}</code> · at most{" "}
        <input
          type="number"
          aria-label="Most uses"
          className="h-5 w-10 rounded border border-border bg-background px-1 text-[11px]"
          value={r.max_uses}
          onChange={(e) => onChange({ ...r, max_uses: num(e.target.value) })}
        />{" "}
        time(s){r.why ? ` · ${r.why}` : ""}
      </p>
    </li>
  );
}

/* ---------------------------------------------------------------- 2. plan */

const ROLE_CLS: Record<string, string> = {
  buffer: "bg-muted border-border",
  vehicle: "bg-background border-reviewed border-2",
  positive: "bg-conflict/70 border-conflict",
  sample: "border-primary",
};

function usePlan(def: ExpDefinition, values?: Record<string, number> | undefined) {
  const body = useMemo(
    () =>
      values
        ? {
            ...def,
            parameters: def.parameters.map((p) =>
              p.name in values ? { ...p, value: values[p.name] ?? p.value } : p,
            ),
          }
        : def,
    [def, values],
  );
  return useQuery({
    queryKey: ["experiment-plan", JSON.stringify(body)],
    queryFn: () => api.experimentPlan(body),
    retry: 0,
    staleTime: 60_000,
  });
}

function PlateMap({ plan }: { plan: ExpPlan }) {
  const max = Math.max(...plan.concentrations_um);
  return (
    <div>
      <div className="grid grid-cols-[16px_repeat(12,minmax(16px,1fr))] gap-1">
        <span />
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className="text-center font-mono text-[9px] text-muted-foreground">
            {i + 1}
          </span>
        ))}
        {"ABCDEFGH".split("").flatMap((row) => [
          <span key={row} className="flex items-center font-mono text-[9px] text-muted-foreground">
            {row}
          </span>,
          ...Array.from({ length: 12 }, (_, i) => {
            const id = `${row}${i + 1}`;
            const w = plan.wells[id];
            const shade =
              w?.role === "sample" && w.conc_um
                ? 0.15 + (0.85 * (Math.log10(w.conc_um) - Math.log10(max) + 4)) / 4
                : 1;
            return (
              <div
                key={id}
                title={`${id}: ${w ? (w.role === "sample" ? `${fmt(w.conc_um, 3)} µM` : w.role) : "empty"}`}
                className={`aspect-square rounded-full border ${w ? ROLE_CLS[w.role] : "border-dashed border-border"}`}
                style={
                  w?.role === "sample"
                    ? {
                        background: `color-mix(in oklab, var(--color-primary) ${Math.round(Math.max(0.1, Math.min(1, shade)) * 100)}%, transparent)`,
                      }
                    : undefined
                }
              />
            );
          }),
        ])}
      </div>
      <p className="mt-3 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <span>● darker blue = higher concentration</span>
        <span className="text-reviewed">○ vehicle (0% effect)</span>
        <span className="text-conflict">● positive control (full effect)</span>
        <span>◌ buffer (outer ring)</span>
      </p>
    </div>
  );
}

function PlanView({
  def,
  values,
}: {
  def: ExpDefinition;
  values?: Record<string, number> | undefined;
}) {
  const q = usePlan(def, values);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const steps = useMemo(() => (q.data ? planToSteps(q.data) : []), [q.data]);
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(
      () =>
        setStep((v) => {
          if (v >= steps.length - 1) {
            setPlaying(false);
            return v;
          }
          return v + 1;
        }),
      350,
    );
    return () => window.clearInterval(t);
  }, [playing, steps.length]);
  if (q.isPending) return <p className="text-sm text-muted-foreground">Checking the plan…</p>;
  if (q.isError)
    return (
      <p role="alert" className="rounded-md border border-destructive p-4 text-sm text-destructive">
        The definition was refused: {(q.error as Error).message}
      </p>
    );
  const p = q.data;
  return (
    <div className="space-y-6">
      {values && (
        <p className="text-xs text-muted-foreground">
          The plan for the next queued run, after your rules were applied to the last result.
        </p>
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          title={p.feasible ? "The robot can run this plan" : "The robot cannot run this plan"}
          note={p.scope}
        >
          <ul className="space-y-2 text-xs">
            {p.checks.map((c) => (
              <li key={c.check} className="flex gap-2">
                <span
                  className={`mt-0.5 shrink-0 font-mono text-[10px] ${c.status === "pass" ? "text-reviewed" : c.status === "fail" ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {c.status === "not_run" ? "not run" : c.status}
                </span>
                <span>
                  <strong>{PLAN_CHECK[c.check] ?? c.check}</strong>
                  <span className="block text-muted-foreground">{c.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs">
            <div>
              <dt className="text-muted-foreground">Concentrations</dt>
              <dd className="font-mono">
                {fmt(p.concentrations_um[0], 3)} → {fmt(p.concentrations_um.at(-1), 3)} µM
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Top dilution tube</dt>
              <dd className="font-mono">{fmt(p.dilution_series.top_tube_um)} µM</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Operations · tips</dt>
              <dd className="font-mono">
                {p.operations} · {p.tips}
              </dd>
            </div>
          </dl>
        </Panel>
        <Panel title="Plate map">
          <PlateMap plan={p} />
        </Panel>
      </div>
      {steps.length > 0 && (
        <Panel
          title="What the robot would do"
          note="The planned moves replayed on the robot model: tip rack, reservoir, wells, waste. Geometry only."
        >
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div className="h-[340px] overflow-hidden rounded-md border border-border bg-workspace">
              <Suspense fallback={<p className="p-4 text-xs text-muted-foreground">Loading…</p>}>
                <LabDeck3D step={step} steps={steps} />
              </Suspense>
            </div>
            <div className="text-xs">
              <div className="flex gap-2">
                <Button size="sm" onClick={() => setPlaying(!playing)}>
                  {playing ? <Pause /> : <Play />} {playing ? "Pause" : "Play"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setStep(0)}>
                  <RotateCcw />
                </Button>
              </div>
              <p className="mt-3 font-mono text-muted-foreground">
                {step + 1} / {steps.length}
              </p>
              <p className="mt-1 font-medium">{steps[step]?.title}</p>
              <p className="text-muted-foreground">{steps[step]?.action}</p>
              {p.robot && (
                <p className="mt-3 text-muted-foreground">
                  Motion check: {p.robot.overall}, {fmt(p.robot.path_length_mm)} mm of travel.
                </p>
              )}
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- 3. run */

function RunView({
  def,
  history,
  setHistory,
  onLog,
}: {
  def: ExpDefinition;
  history: ExpRun[];
  setHistory: (h: ExpRun[]) => void;
  onLog: () => void;
}) {
  const [csv, setCsv] = useState("");
  const [ai, setAi] = useState(false);
  const last = history.at(-1);
  const finished = last && last.decision.status !== "continue";
  const values =
    last?.next_values ?? Object.fromEntries(def.parameters.map((p) => [p.name, p.value]));
  const parsed = parseReadings(csv);
  const stepM = useMutation({
    mutationFn: (b: { readings?: Record<string, number>; synthetic_seed?: number }) =>
      api.experimentStep({ definition: def, history, ai, ...b }),
    onSuccess: (run) => setHistory([...history, run]),
  });
  const nightM = useMutation({
    mutationFn: () => api.experimentOvernight({ definition: def, seed: 0, ai }),
    onSuccess: (out) => {
      setHistory(out.runs);
      onLog();
    },
  });
  const changed = def.parameters.filter((p) => p.role === "varied");
  const error = (stepM.error ?? nightM.error) as Error | null;
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          title={finished ? "This experiment has ended" : `Run ${history.length + 1}: settings`}
          note={
            finished
              ? `${STATUS[last.decision.status]}: ${last.decision.why}. Start again from the example, or change the definition and clear the log.`
              : "The settings for the next run, after your rules have been applied to the last result."
          }
        >
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
            {changed.map((p) => (
              <div key={p.name}>
                <dt className="text-muted-foreground">{p.label}</dt>
                <dd className="font-mono">
                  {fmt(values[p.name], 3)} {p.unit}
                </dd>
              </div>
            ))}
          </dl>
          <label className="mt-4 flex items-center gap-2 text-xs">
            <input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} />
            Ask the AI to review each result (it can only choose among the changes your rules allow;
            needs a model key on the server)
          </label>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              disabled={!!finished || stepM.isPending}
              variant="outline"
              onClick={() => stepM.mutate({ synthetic_seed: history.length })}
            >
              Use synthetic readings (labelled)
            </Button>
            <Button
              disabled={nightM.isPending}
              onClick={() => nightM.mutate()}
              title="Runs the whole loop from the start with SYNTHETIC readings"
            >
              <Moon /> {nightM.isPending ? "Running…" : "Run overnight (synthetic)"}
            </Button>
          </div>
        </Panel>
        <Panel
          title="Your plate-reader results"
          note="Paste or upload one line per well: well,value (for example B3,41250). Header lines are skipped."
        >
          <textarea
            aria-label="Plate-reader readings"
            className={`${input} h-28 py-1 font-mono`}
            value={csv}
            placeholder={"well,value\nB2,52310\nB3,48870\n…"}
            onChange={(e) => setCsv(e.target.value)}
          />
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 hover:border-primary/50">
              <Upload className="size-3.5" /> Upload CSV
              <input
                type="file"
                accept=".csv,.txt,.tsv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void f.text().then(setCsv);
                }}
              />
            </label>
            <span className="text-muted-foreground">
              {Object.keys(parsed.readings).length} wells read
              {parsed.bad.length ? ` · ${parsed.bad.length} line(s) not understood` : ""}
            </span>
            <Button
              size="sm"
              disabled={!!finished || stepM.isPending || Object.keys(parsed.readings).length === 0}
              onClick={() => stepM.mutate({ readings: parsed.readings })}
            >
              Evaluate my readings
            </Button>
          </div>
        </Panel>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive p-3 text-sm text-destructive"
        >
          {error.message}
        </p>
      )}
      {last && <RunResult run={last} def={def} />}
    </div>
  );
}

function RunResult({ run, def }: { run: ExpRun; def: ExpDefinition }) {
  const ev = run.evaluation;
  const v = VERDICT[ev.verdict] ?? VERDICT["pass"]!;
  return (
    <section aria-label="Latest result" className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">Run {run.run}</h2>
        <span className={`evidence-badge ${v.cls}`}>{v.text}</span>
        <span
          className={`evidence-badge ${run.readings_label === "SYNTHETIC" ? "evidence-hypothesis" : "evidence-reviewed"}`}
        >
          {run.readings_label === "SYNTHETIC" ? "SYNTHETIC readings" : "MEASURED readings"}
        </span>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Against your criteria">
          {ev.verdict === "plan_fail" ? (
            <p className="text-xs text-destructive">
              Not run: {ev.failed.map((f) => PLAN_CHECK[f] ?? f).join(", ")}.
            </p>
          ) : (
            <table className="w-full text-xs">
              <tbody className="divide-y divide-border">
                {ev.criteria.map((c) => (
                  <tr key={c.id}>
                    <td className="py-1.5 pr-2">
                      {METRIC[c.metric].label}
                      <span className="block text-[10px] text-muted-foreground">{c.severity}</span>
                    </td>
                    <td className="pr-2 font-mono">{fmt(c.value, 3)}</td>
                    <td className="pr-2 font-mono text-muted-foreground">
                      {c.op === ">=" ? "≥" : "≤"} {c.threshold}
                    </td>
                    <td className={c.pass ? "text-reviewed" : "font-medium text-destructive"}>
                      {c.pass ? "pass" : "fail"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {ev.fit && (
            <p className="mt-3 text-xs text-muted-foreground">
              4PL fit: IC50 {fmt(ev.fit.ic50_um, 3)} µM · Hill slope {fmt(ev.fit.hill, 2)} · top{" "}
              {fmt(ev.fit.top, 3)}% · bottom {fmt(ev.fit.bottom, 3)}%. Measured on{" "}
              {run.readings_label === "SYNTHETIC"
                ? "synthetic values (not a real IC50)"
                : "your readings"}
              .
            </p>
          )}
        </Panel>
        <Panel title="Dose-response">
          {run.readings && ev.fit ? (
            <Curve run={run} />
          ) : (
            <p className="text-xs text-muted-foreground">No curve: the run was not evaluated.</p>
          )}
        </Panel>
      </div>
      <Panel
        title={`Next: ${STATUS[run.decision.status]}`}
        note={`${run.decision.why}. Decided by ${run.decision.decided_by === "ai_review" ? "the AI, within your rules" : "your rules"}${run.decided_note && run.decided_note !== run.decision.decided_by ? ` · ${run.decided_note}` : ""}.`}
      >
        {run.decision.changes.length > 0 ? (
          <ul className="space-y-1.5 text-xs">
            {run.decision.changes.map((c) => (
              <li key={c.rule}>
                <code className="text-muted-foreground">{c.rule}</code>{" "}
                {c.action === "rerun" ? (
                  "repeat with the same settings"
                ) : (
                  <>
                    <strong>{c.label}</strong>: {fmt(c.from, 3)} → {fmt(c.to, 3)} {c.unit}
                  </>
                )}
                {c.why ? <span className="text-muted-foreground"> · {c.why}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No change.</p>
        )}
        {run.decision.rejected.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
            {run.decision.rejected.map((r) => (
              <li key={r.rule}>
                Refused <code>{r.rule}</code>: {r.reason}
              </li>
            ))}
          </ul>
        )}
        {run.decision.ai && (
          <div className="mt-3 rounded-md border border-hypothesis p-3 text-xs">
            <p className="font-semibold text-hypothesis">
              AI review ({run.decision.ai.model}) · {run.decision.ai.label}
            </p>
            <p className="mt-1">{run.decision.ai.reasoning}</p>
            {run.decision.ai.dropped_unoffered.length > 0 && (
              <p className="mt-1 text-muted-foreground">
                Ignored because your rules do not allow them:{" "}
                {run.decision.ai.dropped_unoffered.join(", ")}
              </p>
            )}
          </div>
        )}
        <p className="mt-3 text-[11px] text-muted-foreground">
          Passing runs needed in a row with the same settings: {def.passes_needed}.
        </p>
      </Panel>
    </section>
  );
}

function Curve({ run }: { run: ExpRun }) {
  const { plan, readings = {}, evaluation } = run;
  const fit = evaluation.fit!;
  const mean = (role: string) => {
    const xs = Object.entries(plan.wells)
      .filter(([w, x]) => x.role === role && w in readings)
      .map(([w]) => readings[w]!);
    return xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length);
  };
  const mv = mean("vehicle");
  const mp = mean("positive");
  const pts = Object.entries(plan.wells)
    .filter(([w, x]) => x.role === "sample" && w in readings)
    .map(([w, x]) => [Math.log10(x.conc_um!), (100 * (readings[w]! - mp)) / (mv - mp)] as const);
  const lx = pts.map((p) => p[0]);
  const x0 = Math.min(...lx) - 0.3;
  const x1 = Math.max(...lx) + 0.3;
  const W = 420;
  const H = 220;
  const sx = (x: number) => 36 + ((x - x0) / (x1 - x0)) * (W - 48);
  const sy = (y: number) => 12 + ((120 - y) / 140) * (H - 40);
  const f = (x: number) =>
    fit.bottom + (fit.top - fit.bottom) / (1 + 10 ** ((x - Math.log10(fit.ic50_um)) * fit.hill));
  const line = Array.from({ length: 60 }, (_, i) => x0 + ((x1 - x0) * i) / 59)
    .map((x, i) => `${i ? "L" : "M"}${sx(x).toFixed(1)},${sy(f(x)).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Dose-response curve">
      {[0, 50, 100].map((y) => (
        <g key={y}>
          <line x1={36} x2={W - 12} y1={sy(y)} y2={sy(y)} className="stroke-border" />
          <text x={4} y={sy(y) + 3} className="fill-muted-foreground text-[9px]">
            {y}%
          </text>
        </g>
      ))}
      <path d={line} fill="none" className="stroke-primary" strokeWidth={2} />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={sx(x)} cy={sy(y)} r={3} className="fill-foreground/70" />
      ))}
      <line
        x1={sx(Math.log10(fit.ic50_um))}
        x2={sx(Math.log10(fit.ic50_um))}
        y1={sy(110)}
        y2={sy(-10)}
        strokeDasharray="3 3"
        className="stroke-hypothesis"
      />
      <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-muted-foreground text-[9px]">
        concentration (µM, log scale) · activity in % of vehicle
      </text>
    </svg>
  );
}

/* ---------------------------------------------------------------- 4. log */

function Log({ history, def }: { history: ExpRun[]; def: ExpDefinition }) {
  if (!history.length)
    return (
      <p className="text-sm text-muted-foreground">
        No runs yet. Run one in step 3, or run the whole loop overnight.
      </p>
    );
  const varied = def.parameters.filter((p) => p.role === "varied");
  const last = history.at(-1)!;
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>{STATUS[last.decision.status]}</strong>
        <span className="text-muted-foreground"> · {last.decision.why}</span>
      </p>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[760px] text-xs">
          <thead className="bg-muted/40 text-left text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-normal">Run</th>
              {varied.map((p) => (
                <th key={p.name} className="px-2 font-normal">
                  {p.label} ({p.unit})
                </th>
              ))}
              <th className="px-2 font-normal">Readings</th>
              <th className="px-2 font-normal">Result</th>
              <th className="px-2 font-normal">Failed</th>
              <th className="px-2 font-normal">Then</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {history.map((r) => (
              <tr key={r.run}>
                <td className="px-3 py-2 font-mono">{r.run}</td>
                {varied.map((p) => (
                  <td key={p.name} className="px-2 font-mono">
                    {fmt(r.values[p.name], 3)}
                  </td>
                ))}
                <td className="px-2">{r.readings_label}</td>
                <td className="px-2">{VERDICT[r.evaluation.verdict]?.text}</td>
                <td className="px-2 text-muted-foreground">
                  {r.evaluation.failed.join(", ") || "—"}
                </td>
                <td className="px-2">
                  {r.decision.changes.length
                    ? r.decision.changes
                        .map((c) =>
                          c.action === "rerun"
                            ? "repeat"
                            : `${c.label} → ${fmt(c.to, 3)} ${c.unit}`,
                        )
                        .join("; ")
                    : STATUS[r.decision.status]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
