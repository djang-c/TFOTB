import { useQuery } from "@tanstack/react-query";
import { isTimingResults, summarize, type TimingResults } from "@/lib/timing";

type Journey = {
  measured_at: string;
  runs: number;
  first_request_ms: number;
  all_five_calls_ms: { median: number; p95: number };
  checklist_passed: string;
  base_url: string;
};

/** A missing file on this host answers with the app shell (HTML), so anything that is not the expected JSON is "no data". */
async function optionalJson<T>(path: string, ok: (x: unknown) => x is T): Promise<T | null> {
  try {
    const r = await fetch(path);
    if (!r.ok) return null;
    const x: unknown = await r.json();
    return ok(x) ? x : null;
  } catch {
    return null;
  }
}
const isJourney = (x: unknown): x is Journey =>
  typeof x === "object" && x !== null && "all_five_calls_ms" in x && "checklist_passed" in x;

const STEP_NAME: Record<string, string> = {
  m1: "Who shares our disease characteristics?",
  m2: "What useful work exists?",
  m3: "Who could we approach?",
  m4: "The sourced brief",
};
const min = (m: number) => (m >= 60 ? `${(m / 60).toFixed(1)} h` : `${Math.round(m)} min`);

export function Measured() {
  const journey = useQuery({
    queryKey: ["measured-journey"],
    queryFn: () => optionalJson("/measurements/journey.json", isJourney),
    staleTime: Infinity,
  });
  const people = useQuery({
    queryKey: ["measured-people"],
    queryFn: () =>
      optionalJson<TimingResults>("/measurements/timing-results.json", isTimingResults),
    staleTime: Infinity,
  });
  const j = journey.data;
  const steps = people.data ? summarize(people.data) : [];
  const counted = steps.filter((s) => s.n > 0);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="min-w-0 rounded-lg border border-primary/40 bg-primary/5 p-5">
        <p className="section-kicker">Measured · the product</p>
        {j ? (
          <>
            <p className="mt-2 text-sm leading-6">
              All five calls of Maria&apos;s journey took a median of{" "}
              <strong>{(j.all_five_calls_ms.median / 1000).toFixed(1)} s</strong> (95th percentile{" "}
              {(j.all_five_calls_ms.p95 / 1000).toFixed(1)} s) over {j.runs} runs on the live app. A
              fixed checklist of the answers: <strong>{j.checklist_passed}</strong> pass.
            </p>
            <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
              Measured {j.measured_at.slice(0, 10)} from one client over the internet with{" "}
              <code className="break-all font-mono">scripts/measure_journey.py</code>. It times the
              product only, not what a person does without it.
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            No product measurement file is available here.
          </p>
        )}
      </div>
      <div className="min-w-0 rounded-lg border border-amber-500/40 bg-amber-500/5 p-5">
        <p className="section-kicker">Measured · people</p>
        {counted.length ? (
          <>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="py-1 font-medium">Step</th>
                    <th className="py-1 font-medium">n</th>
                    <th className="py-1 font-medium">By hand</th>
                    <th className="py-1 font-medium">TFOTB</th>
                    <th className="py-1 font-medium">Ratio</th>
                  </tr>
                </thead>
                <tbody>
                  {counted.map((s) => (
                    <tr key={s.step} className="border-t border-border/60">
                      <td className="py-1.5 pr-2">{STEP_NAME[s.step] ?? s.step}</td>
                      <td className="py-1.5 pr-2 font-mono">{s.n}</td>
                      <td className="py-1.5 pr-2 font-mono">{min(s.medianManualMin)}</td>
                      <td className="py-1.5 pr-2 font-mono">{min(s.medianTfotbMin)}</td>
                      <td className="py-1.5 font-mono font-semibold">
                        {s.medianRatio.toFixed(1)}×{" "}
                        <span className="font-normal text-muted-foreground">
                          ({s.minRatio.toFixed(1)}–{s.maxRatio.toFixed(1)})
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
              Medians over pairs where both runs passed the same quality bar. Runs that failed it
              are counted apart: {steps.reduce((a, s) => a + s.excluded, 0)} excluded. Small n: an
              indication, not a population estimate.
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm leading-6">
            <strong>None yet.</strong> The typical-way times below are assumptions until real people
            have been timed on the same tasks. The protocol is in{" "}
            <code className="break-all font-mono">docs/TIMING_STUDY.md</code>; results go in{" "}
            <code className="break-all font-mono">
              frontend/public/measurements/timing-results.json
            </code>{" "}
            and appear here.
          </p>
        )}
      </div>
    </div>
  );
}
