import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, Circle, Gauge, Pause, Play, RotateCcw } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { WellPlate } from "@/components/WellPlate";
import { api } from "@/lib/api";
import { clean } from "@/lib/labels";
import { firstWorkflowStep, runToSteps } from "@/lib/simulation";

const LabDeck3D = lazy(() =>
  import("@/components/LabDeck3D").then((m) => ({ default: m.LabDeck3D })),
);

export const Route = createFileRoute("/simulation")({ ssr: false, component: SimulationPage });

function SimulationPage() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 300_000, retry: 1 });
  const runs = meta.data?.simulations ?? [];
  const [runId, setRunId] = useState<string | null>(null);
  const id =
    runId ?? runs.find((r) => r.spec === "valid_transfer")?.run_id ?? runs[0]?.run_id ?? null;
  const sim = useQuery({
    queryKey: ["simulation", id],
    queryFn: () => api.simulation(id ?? ""),
    enabled: !!id,
    retry: 1,
  });
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const run = sim.data;
  const steps = run ? runToSteps(run) : [firstWorkflowStep];
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
      1400 / speed,
    );
    return () => window.clearInterval(t);
  }, [playing, speed, steps.length]);
  const current = steps[step] ?? firstWorkflowStep;
  const report = run?.report;
  const pass = report?.overall === "pass";
  const choose = (next: string) => {
    setRunId(next);
    setStep(0);
    setPlaying(false);
  };

  if (meta.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The simulation list could not be loaded. Check that the API is running.
      </p>
    );
  return (
    <div className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1440px] border-x border-border">
      <header className="flex flex-col gap-4 border-b border-border px-5 py-6 lg:flex-row lg:items-end lg:px-7">
        <div>
          <p className="section-kicker">
            Robotics replay /{" "}
            {report?.simulator_name ? `${report.simulator_name} ${report.simulator_version}` : "…"}
          </p>
          <h1 className="mt-2 text-2xl font-semibold">Bounded liquid transfer</h1>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-muted-foreground">
            {(report?.scope_label ?? "Workflow simulation only; not wet-lab validated").replace(
              /\.?$/,
              ".",
            )}{" "}
            A pass checks geometry and resources only. It says nothing about biology or whether a
            treatment works. {run?.label}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 lg:ml-auto">
          {runs.map((r) => (
            <Button
              key={r.run_id}
              size="sm"
              variant={r.run_id === id ? "default" : "outline"}
              onClick={() => choose(r.run_id)}
              className="font-mono text-[10px]"
            >
              {r.spec ?? r.run_id}
            </Button>
          ))}
          {report && (
            <span
              className={`flex items-center gap-2 border px-2.5 py-1 text-xs ${pass ? "border-reviewed text-reviewed" : "border-conflict text-conflict"}`}
            >
              {pass ? <Check className="size-3" /> : <AlertTriangle className="size-3" />}
              {pass ? "Checks passing" : "Run failed (intended)"}
            </span>
          )}
        </div>
      </header>
      {sim.isError && (
        <p role="alert" className="p-6 text-sm text-destructive">
          This run could not be loaded.
        </p>
      )}
      <div className="grid xl:grid-cols-[330px_minmax(0,1fr)]">
        <aside className="border-b border-border xl:border-b-0 xl:border-r">
          <div className="border-b border-border p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Operation trace</h2>
              <span className="font-mono text-xs text-muted-foreground">
                {step + 1} / {steps.length}
              </span>
            </div>
            <div className="mt-4 h-px bg-border">
              <div
                className="h-px bg-primary transition-all"
                style={{ width: `${((step + 1) / steps.length) * 100}%` }}
              />
            </div>
          </div>
          <div>
            {steps.map((item, index) => (
              <Button
                key={item.id}
                variant="ghost"
                onClick={() => {
                  setStep(index);
                  setPlaying(false);
                }}
                className={`h-auto w-full justify-start rounded-none border-b border-border p-4 text-left whitespace-normal ${index === step ? "bg-accent" : ""}`}
              >
                <span
                  className={`grid size-6 shrink-0 place-items-center rounded-full border font-mono text-[9px] ${item.failed ? "border-conflict text-conflict" : index < step ? "border-reviewed bg-reviewed text-primary-foreground" : index === step ? "border-primary text-primary" : "border-border text-muted-foreground"}`}
                >
                  {item.failed ? "!" : index < step ? <Check className="size-3" /> : item.id}
                </span>
                <span className="min-w-0">
                  <strong className="block text-xs">{item.title}</strong>
                  <span className="mt-1 block font-mono text-[9px] text-muted-foreground">
                    {item.op} · {item.endMm.join(", ")} mm
                  </span>
                </span>
                <span className="ml-auto font-mono text-[9px] text-muted-foreground">
                  {item.duration}
                </span>
              </Button>
            ))}
          </div>
        </aside>
        <section className="min-w-0">
          <div className="grid border-b border-border lg:grid-cols-[1.25fr_.75fr]">
            <div className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="section-kicker">Replay of a recorded run</p>
                  <h2 className="mt-1 text-lg font-semibold">Articulated liquid handler</h2>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground">X/Y/Z · mm</span>
              </div>
              <Suspense fallback={<div className="h-[390px] border border-border bg-workspace" />}>
                <LabDeck3D step={step} steps={steps} />
              </Suspense>
            </div>
            <div className="border-t border-border p-5 lg:border-l lg:border-t-0">
              <div className="mb-4">
                <p className="section-kicker">Destination plate</p>
                <h2 className="mt-1 text-lg font-semibold">96-well state</h2>
              </div>
              <WellPlate step={step} steps={steps} />
              <div className="mt-4 flex flex-wrap gap-3 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Circle className="size-2 fill-primary text-primary" />
                  Current
                </span>
                <span className="flex items-center gap-1">
                  <Circle className="size-2 fill-primary/30 text-primary/30" />
                  Processed
                </span>
                <span className="flex items-center gap-1">
                  <Circle className="size-2 fill-background text-border" />
                  Empty
                </span>
              </div>
            </div>
          </div>
          <div className="grid lg:grid-cols-[1fr_300px]">
            <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
              <div className="flex items-center gap-3">
                <Button
                  size="icon"
                  onClick={() => setPlaying(!playing)}
                  aria-label={playing ? "Pause replay" : "Play replay"}
                >
                  {playing ? <Pause /> : <Play />}
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    setStep(0);
                    setPlaying(false);
                  }}
                  aria-label="Restart replay"
                >
                  <RotateCcw />
                </Button>
                <input
                  aria-label="Workflow progress"
                  type="range"
                  min="0"
                  max={steps.length - 1}
                  value={step}
                  onChange={(e) => {
                    setStep(Number(e.target.value));
                    setPlaying(false);
                  }}
                  className="mx-2 flex-1 accent-primary"
                />
                <span className="font-mono text-xs">{current.duration}</span>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Replay speed</span>
                {[0.5, 1, 2].map((v) => (
                  <Button
                    key={v}
                    variant={speed === v ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => setSpeed(v)}
                    className="font-mono text-[10px]"
                  >
                    {v}×
                  </Button>
                ))}
              </div>
            </div>
            <div className="p-5">
              <div className="flex items-center gap-2 text-xs font-semibold">
                <Gauge className="size-4 text-primary" />
                Run ledger
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div>
                  <dt className="text-muted-foreground">Source</dt>
                  <dd className="mt-1 font-mono">{report?.ledger_after.source_ul ?? "—"} µL</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Tips left</dt>
                  <dd className="mt-1 font-mono">{report?.ledger_after.tips_available ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Path</dt>
                  <dd className="mt-1 font-mono">
                    {report ? report.path_length_mm.toFixed(1) : "—"} mm
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Failures</dt>
                  <dd
                    className={`mt-1 font-mono ${report && report.failures.length > 0 ? "text-conflict" : "text-reviewed"}`}
                  >
                    {report?.failures.length ?? "—"}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
          <div className="border-t border-border p-5">
            <p className="font-mono text-[10px] text-primary">
              OP {String(current.id).padStart(2, "0")} · {current.op}
            </p>
            <h3 className="mt-2 text-sm font-semibold">{current.title}</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {current.action}. Target position {current.endMm.join(", ")} mm.
            </p>
          </div>
          {report && (
            <div className="grid gap-px border-t border-border bg-border md:grid-cols-2">
              <div className="bg-background p-5">
                <h3 className="text-sm font-semibold">Checks</h3>
                <ul className="mt-3 space-y-2 text-xs">
                  {report.checks.map((c) => (
                    <li key={c.check_name}>
                      <span
                        className={`font-mono text-[10px] ${c.status === "pass" ? "text-reviewed" : c.status === "fail" ? "text-conflict" : "text-muted-foreground"}`}
                      >
                        {c.status.replace("_", " ")}
                      </span>{" "}
                      <b>{c.check_name.replaceAll("_", " ")}</b>
                      <span className="block text-muted-foreground">{c.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="bg-background p-5">
                <h3 className="text-sm font-semibold">Failures</h3>
                {report.failures.length === 0 ? (
                  <p className="mt-3 text-xs text-muted-foreground">None recorded.</p>
                ) : (
                  <ul className="mt-3 space-y-2 text-xs">
                    {report.failures.map((f, i) => (
                      <li key={i}>
                        <b>{f.check.replaceAll("_", " ")}</b>
                        {f.op_index !== undefined && ` at operation ${f.op_index + 1}`}
                        <span className="block text-muted-foreground">{f.reason}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {run?.linked_entity && (
                  <p className="mt-4 text-[11px] text-muted-foreground">
                    Linked to the demo entry{" "}
                    <Link
                      to="/explorer"
                      search={{ id: run.linked_entity.id }}
                      className="underline"
                    >
                      {clean(run.linked_entity.label)}
                    </Link>{" "}
                    as a computer prediction. It never counts as biological support.
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
