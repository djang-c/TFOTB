import { Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  compareJourney,
  fmtX,
  HOURS_PER_DAY,
  PERSONAS,
  type Overrides,
  type Persona,
} from "@/lib/journey";

/** Our stand-in for Maria's disease: the seed disease the project has read papers about. */
const MARIA_DISEASE = { id: "MONDO:0008767", label: "CLN3 disease" };

type Timed<T> = { ms: number; data: T };
async function timed<T>(f: () => Promise<T>): Promise<Timed<T>> {
  const t = performance.now();
  const data = await f();
  return { ms: performance.now() - t, data };
}

function useJourneyRun() {
  return useMutation({
    mutationFn: async () => {
      const id = MARIA_DISEASE.id;
      const [related, groups, collaborators, assets, actions] = await Promise.all([
        timed(() => api.relatedDiseases(id)),
        timed(() => api.groups(id)),
        timed(() => api.collaborators(id)),
        timed(() => api.assets(id)),
        timed(() => api.actions(id)),
      ]);
      return { related, groups, collaborators, assets, actions };
    },
  });
}

const sec = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

function Answer({
  q,
  ms,
  children,
  to,
}: {
  q: string;
  ms: number;
  children: React.ReactNode;
  to: string;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/90 p-4 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <p className="section-kicker">{q}</p>
        <span className="font-mono text-[11px] text-muted-foreground">{sec(ms)}</span>
      </div>
      <div className="mt-2 leading-6">{children}</div>
      <Link
        to="/entity/$id"
        params={{ id: MARIA_DISEASE.id }}
        hash={to}
        className="mt-2 inline-block text-xs text-primary underline-offset-2 hover:underline"
      >
        Open it on the dossier →
      </Link>
    </div>
  );
}

export function MariaJourneyLive() {
  const run = useJourneyRun();
  const d = run.data;
  const top = d?.related.data.diseases[0];
  const topReason = top?.reasons.find((r) => r.kind === "mechanism") ?? top?.reasons[0];
  const brief = d?.actions.data.cards.find((c) => c.kind === "evidence_brief");
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={run.isPending} onClick={() => run.mutate()}>
          <Play /> {run.isPending ? "Running…" : `Run Maria's journey for ${MARIA_DISEASE.label}`}
        </Button>
        <span className="text-xs text-muted-foreground">
          Five real calls to this site's API. The times are measured in your browser.
        </span>
      </div>
      {run.isError && (
        <p role="alert" className="mt-3 text-xs text-destructive">
          The API did not answer, so there is nothing to show yet.
        </p>
      )}
      {d && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Answer q="1 · Who shares our disease characteristics?" ms={d.related.ms} to="related">
            {d.related.data.total} related diseases. First: <strong>{top?.label}</strong>
            {topReason ? `, because ${topReason.detail ?? topReason.label}` : ""}.
          </Answer>
          <Answer
            q="2 · What useful work exists?"
            ms={Math.max(d.groups.ms, d.assets.ms)}
            to="assets"
          >
            {d.groups.data.groups.length} patient groups (
            {d.groups.data.groups.filter((g) => g.registry_url).length} with a registry link) and{" "}
            {d.assets.data.assets.length} matched studies.
          </Answer>
          <Answer q="3 · Who could we approach?" ms={d.collaborators.ms} to="collaborators">
            {d.collaborators.data.items.length} researchers from the papers behind the claims,{" "}
            {d.collaborators.data.items.filter((c) => c.orcid).length} matched by ORCID.
          </Answer>
          <Answer q="4 · What do we do together next?" ms={d.actions.ms} to="actions">
            {brief
              ? `A sourced evidence brief, ready to export. Next step it names: “${brief.this_week}”`
              : "No brief could be built from what is stored."}
          </Answer>
        </div>
      )}
    </div>
  );
}

export function PersonaTable() {
  const [over, setOver] = useState<Overrides>({});
  const [stress, setStress] = useState(3);
  const set = (id: string, key: "manualDays" | "assistedHours", raw: string) =>
    setOver((o) => ({ ...o, [id]: { ...o[id], [key]: raw === "" ? 0 : Number(raw) } }));
  return (
    <div>
      <div className="space-y-5">
        {PERSONAS.map((p) => (
          <PersonaCard key={p.key} p={p} over={over} set={set} stress={stress} />
        ))}
      </div>
      <label className="mt-5 flex flex-wrap items-center gap-2 text-sm" htmlFor="stress">
        <span>Stress test: what if checking the sources takes</span>
        <input
          id="stress"
          type="number"
          min={1}
          step="0.5"
          value={stress}
          onChange={(e) => setStress(Math.max(1, Number(e.target.value) || 1))}
          className="w-16 rounded-md border border-border bg-background px-2 py-1 font-mono text-sm"
        />
        <span>times as long as assumed?</span>
      </label>
    </div>
  );
}

function PersonaCard({
  p,
  over,
  set,
  stress,
}: {
  p: Persona;
  over: Overrides;
  set: (id: string, key: "manualDays" | "assistedHours", raw: string) => void;
  stress: number;
}) {
  const r = compareJourney(p, over, stress);
  return (
    <section
      aria-label={p.name}
      className="rounded-lg border border-border/70 bg-background/90 p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="section-kicker">
            {p.name} · {p.role}
          </p>
          <p className="mt-2 text-sm italic leading-6 text-muted-foreground">
            “{p.pain}” <span className="not-italic">(challenge brief)</span>
          </p>
          <p className="mt-2 text-sm">
            <strong>Milestone:</strong> {p.milestone}
          </p>
        </div>
        <div className="text-right" role="status">
          <div
            className={`font-mono text-4xl font-semibold ${r.speedup >= 10 ? "text-primary" : ""}`}
          >
            {fmtX(r.speedup)}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {r.manualDays.toFixed(0)} working days → {r.assistedHours.toFixed(1)} working hours
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            10× holds unless checking takes {r.headroom.toFixed(1)}× longer. At {stress}×:{" "}
            <strong>{fmtX(r.stressed)}</strong>
          </div>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">Step</th>
              <th className="py-1 pr-3 font-medium">The typical way (working days)</th>
              <th className="py-1 font-medium">With TFOTB (working hours)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60 align-top">
            {p.steps.map((s) => (
              <tr key={s.id}>
                <td className="py-3 pr-3">
                  <div className="font-medium">{s.question}</div>
                </td>
                <td className="py-3 pr-3">
                  <input
                    aria-label={`${s.question} typical days`}
                    type="number"
                    min={0}
                    step="any"
                    value={over[s.id]?.manualDays ?? s.manualDays}
                    onChange={(e) => set(s.id, "manualDays", e.target.value)}
                    className="w-20 rounded-md border border-border bg-background px-2 py-1 font-mono text-sm"
                  />
                  <span
                    className={`ml-2 rounded-full border px-2 py-0.5 text-[10px] ${s.basis === "brief" ? "border-primary/40 bg-primary/10 text-primary" : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"}`}
                  >
                    {s.basis === "brief" ? "From the brief" : "Assumption"}
                  </span>
                  <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">
                    {s.manualHow}
                  </p>
                </td>
                <td className="py-3">
                  <input
                    aria-label={`${s.question} hours with TFOTB`}
                    type="number"
                    min={0}
                    step="any"
                    value={over[s.id]?.assistedHours ?? s.assistedHours}
                    onChange={(e) => set(s.id, "assistedHours", e.target.value)}
                    className="w-20 rounded-md border border-border bg-background px-2 py-1 font-mono text-sm"
                  />
                  <span className="ml-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-400">
                    Assumption
                  </span>
                  <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">{s.siteHow}</p>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
        <strong
          className={p.built === "built" ? "text-primary" : "text-amber-700 dark:text-amber-400"}
        >
          {p.built === "built" ? "Built." : "Partly built."}
        </strong>{" "}
        {p.builtNote}
      </p>
    </section>
  );
}

export const WORKING_DAY = `${HOURS_PER_DAY}-hour working day`;
