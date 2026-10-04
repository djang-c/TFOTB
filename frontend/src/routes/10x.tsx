import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Moon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  breakEvenTurnaround,
  compare,
  DEFAULTS,
  fmtDays,
  fmtX,
  SCENARIOS,
  type TenxInputs,
} from "@/lib/tenx";

export const Route = createFileRoute("/10x")({
  ssr: false,
  head: () => ({ meta: [{ title: "10× case — The Flight of the Buffalo" }] }),
  component: TenxPage,
});

type Basis = "assumption" | "site";
const BASIS: Record<Basis, { label: string; cls: string }> = {
  assumption: {
    label: "Assumption",
    cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  },
  site: { label: "Run on this site", cls: "border-primary/40 bg-primary/10 text-primary" },
};

const FIELDS: {
  key: keyof TenxInputs;
  label: string;
  unit: string;
  basis: Basis;
  note: string;
  group: "A" | "B";
}[] = [
  {
    key: "manualBriefDays",
    label: "Build a sourced evidence brief by hand",
    unit: "working days",
    basis: "assumption",
    group: "A",
    note: "Search, read, reconcile names, record the source of each statement. Not measured. The plan is to time real people on 2–3 briefs.",
  },
  {
    key: "verifyHours",
    label: "Check the sources of the brief the site assembled",
    unit: "working hours",
    basis: "assumption",
    group: "A",
    note: "Each claim opens its quote and paper. Someone still has to read them.",
  },
  {
    key: "defineDays",
    label: "Define the experiment",
    unit: "working days",
    basis: "assumption",
    group: "B",
    note: "Parameters, limits, pass criteria and what to change on failure. The same either way: automation does not remove it.",
  },
  {
    key: "runsNeeded",
    label: "Runs until every pass criterion is met",
    unit: "runs",
    basis: "site",
    group: "B",
    note: "From the overnight loop on this site, which uses SYNTHETIC readings. Run it below to refresh this number.",
  },
  {
    key: "manualTurnaroundDays",
    label: "Between two manual runs: plan, book, run, read, analyse, decide",
    unit: "working days",
    basis: "assumption",
    group: "B",
    note: "The number that matters most. It depends on the lab: see the starting points below.",
  },
  {
    key: "runHours",
    label: "Robot time for one run",
    unit: "hours",
    basis: "assumption",
    group: "B",
    note: "Dispensing a plate takes 1–3 minutes (NIH Assay Guidance Manual), so incubation dominates.",
  },
  {
    key: "nightHours",
    label: "Hours of the night the robot may run unattended",
    unit: "hours",
    basis: "assumption",
    group: "B",
    note: "Needs a lab that allows unattended runs.",
  },
  {
    key: "reviewDays",
    label: "Review the finished result",
    unit: "working days",
    basis: "assumption",
    group: "B",
    note: "A person decides whether the result is real. The loop only decides what to run next.",
  },
];

const ANCHORS = [
  {
    fact: "A standard assay validation includes a plate-uniformity study over at least 3 days.",
    source: "NIH Assay Guidance Manual, HTS Assay Validation (NBK83783)",
    use: "Why a manual route cannot be much shorter than a few days per validation step.",
  },
  {
    fact: "Dispensing across a whole plate takes 1–3 minutes.",
    source: "NIH Assay Guidance Manual, Basics of Assay Equipment (NBK92014)",
    use: "Why a run is dominated by incubation, not by the robot.",
  },
  {
    fact: "A mobile robot chemist ran 688 experiments in 8 days, unattended, searching a 10-variable space.",
    source: "Burger et al., Nature 2020, PMID 32641813 (materials chemistry, not biology)",
    use: "Shows that closed-loop operation over days has been done. It is a different system and says nothing about ours.",
  },
  {
    fact: "Choosing experiments intelligently cut the cost of a yeast study by 3-fold against the cheapest strategy and 100-fold against random.",
    source: "King et al., Nature 2004, PMID 14724639 (cost, one system)",
    use: "Precedent for the idea. It is a cost result, not a time result.",
  },
];

const NEXT = [
  "Time 2–3 people building the same evidence brief by hand and with the site, against one quality rubric. Report the sample size and the setup time.",
  "Replace the synthetic readings with a real plate reader and liquid handler, and count how many runs a real compound needs.",
  "Measure how long the manual turnaround really is in two or three labs. It is the assumption the whole case rests on.",
  "Check that the loop's changes are ones a scientist would accept, and that a pass does not hide a bad assay.",
  "Test with a patient group whether the brief changes what they do next.",
];

function Bar({
  label,
  days,
  max,
  tone,
}: {
  label: string;
  days: number;
  max: number;
  tone: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono font-semibold">{fmtDays(days)}</span>
      </div>
      <div className="mt-1.5 h-3 rounded-full bg-muted">
        <div
          className={`h-3 rounded-full ${tone}`}
          style={{ width: `${max > 0 ? Math.max(2, (days / max) * 100) : 0}%` }}
        />
      </div>
    </div>
  );
}

function TenxPage() {
  const [inputs, setInputs] = useState<TenxInputs>(DEFAULTS);
  const [scenario, setScenario] = useState<string | null>("base");
  const example = useQuery({ queryKey: ["experiment-example"], queryFn: api.experimentExample });
  const loop = useMutation({
    mutationFn: () =>
      api.experimentOvernight({ definition: example.data!.definition, seed: 0, ai: false }),
    onSuccess: (o) => setInputs((v) => ({ ...v, runsNeeded: o.runs.length })),
  });
  const r = compare(inputs);
  const t = breakEvenTurnaround(inputs);
  const meets = r.speedup >= 10;
  const set = (key: keyof TenxInputs, raw: string) => {
    setScenario(null);
    setInputs((v) => ({ ...v, [key]: raw === "" ? 0 : Number(raw) }));
  };
  const max = Math.max(r.manualDays, r.assistedDays, 1);
  return (
    <div className="mx-auto max-w-[1100px] px-5 py-10 sm:px-8">
      <header className="border-b border-border pb-8">
        <p className="section-kicker">10× case · from a lead to a decision-ready result</p>
        <h1 className="mt-2 text-3xl font-semibold">
          Could this get a rare-disease lead to its first real result 10× faster?
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
          The answer depends on how slow the manual route is, so this page shows the arithmetic and
          lets you change every assumption. Nothing here is a measured result. The milestone is not
          a treatment or a trial: it is a sourced evidence brief for a lead, followed by a
          quality-checked dose-response for it.
        </p>
      </header>

      <section aria-labelledby="route" className="mt-8">
        <h2 id="route" className="text-xl font-semibold">
          The two routes
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-border/60 bg-muted/30 p-5">
            <p className="section-kicker">Today, by hand</p>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm leading-6">
              <li>Search papers and databases, reconcile names, write the brief.</li>
              <li>Define the experiment.</li>
              <li>
                Run, read, analyse, decide one change, book the robot again. Repeat until the plate
                passes.
              </li>
              <li>Review the result.</li>
            </ol>
          </div>
          <div className="rounded-lg border border-primary/40 bg-primary/5 p-5">
            <p className="section-kicker">With TFOTB</p>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm leading-6">
              <li>
                <Link to="/" className="text-primary underline-offset-2 hover:underline">
                  The dossier
                </Link>{" "}
                assembles the connection with a source behind every statement. A person checks them.
              </li>
              <li>The researcher defines the experiment, with limits, pass criteria and rules.</li>
              <li>
                <Link to="/simulation" className="text-primary underline-offset-2 hover:underline">
                  The loop
                </Link>{" "}
                runs overnight, scores each run, and changes only what the rules allow.
              </li>
              <li>A person reviews the result in the morning.</li>
            </ol>
          </div>
        </div>
      </section>

      <section
        aria-labelledby="result"
        className="mt-10 rounded-lg border border-border bg-background p-6"
      >
        <h2 id="result" className="text-xl font-semibold">
          What the arithmetic says
        </h2>
        <div className="mt-4 grid gap-6 md:grid-cols-[1fr_auto] md:items-center">
          <div className="space-y-4">
            <Bar label="By hand" days={r.manualDays} max={max} tone="bg-muted-foreground/60" />
            <Bar label="With TFOTB" days={r.assistedDays} max={max} tone="bg-primary" />
          </div>
          <div className="text-center md:px-8" role="status" aria-live="polite">
            <div className={`font-mono text-5xl font-semibold ${meets ? "text-primary" : ""}`}>
              {fmtX(r.speedup)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {meets ? "meets the 10× goal on these inputs" : "falls short of 10× on these inputs"}
            </div>
          </div>
        </div>
        <ul className="mt-6 space-y-2 border-t border-border/60 pt-5 text-sm leading-6">
          <li>
            <strong>What 10× needs.</strong>{" "}
            {meets
              ? "These inputs reach it."
              : t === null
                ? "No manual turnaround is needed to reach it."
                : `With everything else held, the manual turnaround would have to be about ${fmtDays(t)} between runs.`}{" "}
            {inputs.manualTurnaroundDays < 5 &&
              !meets &&
              "That is typical of a shared facility where robot time is booked in slots, not of a lab with its own robot."}
          </li>
          <li>
            <strong>The ceiling.</strong> Defining the experiment, checking the sources and
            reviewing the result still take people {fmtDays(r.fixedDays)}. Even if the loop took no
            time, the speedup could not pass <span className="font-mono">{fmtX(r.ceiling)}</span> on
            these inputs. Automation shortens the repeating part, not the thinking.
          </li>
          <li>
            <strong>The loop.</strong> {Math.round(inputs.runsNeeded)} runs fit in {r.nights} night
            {r.nights === 1 ? "" : "s"} ({r.runsPerNight} per night).
          </li>
        </ul>
      </section>

      <section aria-labelledby="assume" className="mt-10">
        <h2 id="assume" className="text-xl font-semibold">
          The assumptions
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Change any number. Starting points for the manual turnaround:
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              type="button"
              aria-pressed={scenario === s.key}
              onClick={() => {
                setScenario(s.key);
                setInputs((v) => ({ ...v, ...s.inputs }));
              }}
              className={`rounded-md border px-3 py-1.5 text-left text-sm ${scenario === s.key ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary/50"}`}
            >
              <span className="block font-medium">{s.label}</span>
              <span className="block text-[11px] opacity-80">{s.note}</span>
            </button>
          ))}
        </div>
        <div className="mt-5 grid gap-6 md:grid-cols-2">
          {(["A", "B"] as const).map((g) => (
            <div key={g}>
              <p className="section-kicker">
                {g === "A" ? "A · Evidence brief" : "B · Dose-response for the lead"}
              </p>
              <div className="mt-2 divide-y divide-border/60 rounded-lg border border-border/60">
                {FIELDS.filter((f) => f.group === g).map((f) => (
                  <div key={f.key} className="p-4">
                    <label
                      className="flex items-start justify-between gap-3 text-sm"
                      htmlFor={`f-${f.key}`}
                    >
                      <span>{f.label}</span>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${BASIS[f.basis].cls}`}
                      >
                        {BASIS[f.basis].label}
                      </span>
                    </label>
                    <div className="mt-2 flex items-center gap-2">
                      <input
                        id={`f-${f.key}`}
                        type="number"
                        min={0}
                        step="any"
                        value={inputs[f.key]}
                        onChange={(e) => set(f.key, e.target.value)}
                        className="w-24 rounded-md border border-border bg-background px-2 py-1 font-mono text-sm"
                      />
                      <span className="text-xs text-muted-foreground">{f.unit}</span>
                    </div>
                    <p className="mt-2 text-[11px] leading-5 text-muted-foreground">{f.note}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            disabled={!example.data || loop.isPending}
            onClick={() => loop.mutate()}
          >
            <Moon />{" "}
            {loop.isPending ? "Running…" : "Run the overnight loop to get the number of runs"}
          </Button>
          {loop.isSuccess && (
            <span className="text-xs text-muted-foreground" role="status">
              The loop reached a passing run after {loop.data.runs.length} runs (SYNTHETIC
              readings).
            </span>
          )}
          {loop.isError && (
            <span role="alert" className="text-xs text-destructive">
              The experiment service did not answer, so the number of runs is unchanged.
            </span>
          )}
        </div>
      </section>

      <section aria-labelledby="anchors" className="mt-10">
        <h2 id="anchors" className="text-xl font-semibold">
          What the assumptions lean on
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Opened and checked. These are different systems from ours, so they give context, not
          support for our numbers.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {ANCHORS.map((a) => (
            <div
              key={a.source}
              className="rounded-lg border border-border/60 bg-muted/30 p-4 text-sm"
            >
              <p className="leading-6">{a.fact}</p>
              <p className="mt-2 text-[11px] text-muted-foreground">{a.source}</p>
              <p className="mt-1 text-[11px] leading-5">{a.use}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="next" className="mt-10 grid gap-6 md:grid-cols-2">
        <div>
          <h2 id="next" className="text-xl font-semibold">
            What must be validated next
          </h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6">
            {NEXT.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/30 p-5">
          <h2 className="text-xl font-semibold">What this does not claim</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6">
            <li>No treatment timeline and no clinical benefit.</li>
            <li>
              No biology: the readings in the loop are synthetic and say nothing about any compound.
            </li>
            <li>
              No measured speedup. If real timings come in under 10×, this page should say so.
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
