import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Moon } from "lucide-react";
import { useState } from "react";
import { MariaJourneyLive, PersonaTable } from "@/components/MariaJourney";
import { Measured } from "@/components/Measured";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  breakEvenTurnaround,
  compare,
  DEFAULTS,
  fmtDays,
  fmtX,
  HEADLINE,
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
  const [inputs, setInputs] = useState<TenxInputs>({ ...DEFAULTS, ...HEADLINE.inputs });
  const [scenario, setScenario] = useState<string | null>(HEADLINE.key);
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
        <p className="section-kicker">10× case · Maria, Devon, Priya and Dr. Osei</p>
        <h1 className="mt-2 text-3xl font-semibold">
          How much faster does Maria get from her disease to a sourced proposal for a partner?
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
          The challenge brief asks for one meaningful milestone, the typical timeline against our
          route, and the assumptions behind a 10× claim. The typical way is what the brief describes
          for each person: assembling everything from scratch, one disease at a time. Our route is
          this product. Every time below is an editable assumption unless it says it comes from the
          brief, and none is measured on real people yet.
        </p>
      </header>

      <section aria-labelledby="live" className="mt-8">
        <h2 id="live" className="text-xl font-semibold">
          Maria's journey, run for real
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The brief's three questions plus the next step, answered by this product for CLN3 disease,
          our seed disease.
        </p>
        <div className="mt-4">
          <MariaJourneyLive />
        </div>
      </section>

      <section aria-labelledby="measured" className="mt-10">
        <h2 id="measured" className="text-xl font-semibold">
          What has been measured
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The product side is measured. The typical-way side is only measured once people have been
          timed.
        </p>
        <div className="mt-4">
          <Measured />
        </div>
      </section>

      <section aria-labelledby="people" className="mt-10">
        <h2 id="people" className="text-xl font-semibold">
          The typical way against TFOTB, for each person in the brief
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The product answers in about 2.5 seconds (measured on the live app). What is left is a
          person checking the sources, so that is the time on the TFOTB side. Change any number.
        </p>
        <div className="mt-4">
          <PersonaTable />
        </div>
      </section>

      <section aria-labelledby="after" className="mt-14 border-t border-border pt-8">
        <p className="section-kicker">Stretch goal · propose an experiment</p>
        <h2 id="after" className="mt-2 text-2xl font-semibold">
          After the proposal: testing the lead in the lab
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-muted-foreground">
          Once Maria has a partner and a lead, the next milestone is a first quality-checked
          dose-response. This part compares a manual run-by-run route with the overnight loop on the
          Simulation page. It is a separate model with its own assumptions.
        </p>
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

      <section aria-labelledby="where" className="mt-10">
        <h2 id="where" className="text-xl font-semibold">
          Where 10× holds, and where it does not
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The same loop and the same other inputs, in three kinds of lab. Only the wait between
          manual runs changes.
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {SCENARIOS.map((s) => {
            const x = compare({ ...inputs, ...s.inputs });
            return (
              <div
                key={s.key}
                className={`rounded-lg border p-4 ${x.speedup >= 10 ? "border-primary/50 bg-primary/5" : "border-border/60 bg-muted/30"}`}
              >
                <div className="font-mono text-3xl font-semibold">{fmtX(x.speedup)}</div>
                <div className="mt-1 text-sm font-medium">{s.label}</div>
                <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                  {fmtDays(x.manualDays)} by hand, {fmtDays(x.assistedDays)} with TFOTB. {s.note}
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-sm leading-6">
          The case: groups without a robot of their own, which is most patient-led efforts, wait for
          booked robot time between every run. That wait is what the overnight loop removes, so 10×
          or more holds there. In a lab with its own robot it is about 6×. Which one applies is what
          must be measured.
        </p>
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
            className="h-auto min-h-8 whitespace-normal py-1.5 text-left"
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
