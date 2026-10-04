import Link from "next/link";
import { notFound } from "next/navigation";
import { api, ApiError, enc } from "@/lib/api";
import { ApiDown } from "@/components/ApiDown";
import { SimReplayLoader } from "@/components/SimReplayLoader";

const specName = (spec?: string) => (spec ? spec.charAt(0).toUpperCase() + spec.slice(1).replaceAll("_", " ") : "Run");

export default async function SimulationPage(props: PageProps<"/simulation/[id]">) {
  const id = decodeURIComponent((await props.params).id);
  let run, meta;
  try {
    [run, meta] = await Promise.all([api.simulation(id), api.meta()]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ApiDown what={id} />;
  }
  const r = run.report;
  const before = flatLedger(r.ledger_before);
  const after = flatLedger(r.ledger_after);
  const tone = { pass: "text-pass", fail: "text-fail", not_modeled: "text-muted" };
  const mark = { pass: "✓", fail: "✕", not_modeled: "—" };

  return (
    <main className="mx-auto max-w-[1240px] px-4 py-8">
      <p className="text-sm text-muted">
        {run.linked_entity && <><Link className="ref" href={`/entity/${enc(run.linked_entity.id)}`}>{run.linked_entity.label}</Link> / </>}
        workflow simulation
      </p>
      <h1 className="mt-1 text-[32px] font-semibold leading-tight tracking-tight">Can the robot run this plate layout?</h1>
      <p className="mt-2 max-w-[70ch] text-muted">
        A liquid-transfer workflow checked in MuJoCo before anyone books lab time. It tests motion
        and volume bookkeeping only. {r.scope_label}.
      </p>

      <nav className="mt-5 flex gap-2 text-sm" aria-label="Recorded runs">
        {(meta.simulations ?? []).map((s) => (
          <Link key={s.run_id} href={`/simulation/${enc(s.run_id)}`}
            className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 ${s.run_id === id ? "border-ink bg-ink text-white" : "border-rule bg-sheet text-ink hover:border-ink"}`}>
            <span aria-hidden className={s.overall === "pass" ? "text-pass" : "text-fail"}>{s.overall === "pass" ? "✓" : "✕"}</span>
            {specName(s.spec)}
          </Link>
        ))}
      </nav>

      <div className="mt-4 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <SimReplayLoader run={run} />

        <aside className="space-y-5 text-sm">
          <div className={`rounded-md border-2 bg-sheet px-4 py-3 ${r.overall === "pass" ? "border-pass" : "border-fail"}`}>
            <p className={`text-2xl font-semibold ${r.overall === "pass" ? "text-pass" : "text-fail"}`}>
              {r.overall === "pass" ? "Workflow passed its checks" : "Workflow stopped"}
            </p>
            {r.failures.map((f, i) => <p key={i} className="mt-1">{f.reason}</p>)}
            <p className="mt-2 text-xs text-muted">A pass never raises confidence in the biology.</p>
          </div>

          <section>
            <h2 className="mb-1 font-semibold">Checks</h2>
            <ul className="divide-y divide-rule rounded-md border border-rule bg-sheet">
              {r.checks.map((c) => (
                <li key={c.check_name} className="flex gap-2 px-3 py-1.5">
                  <span className={`w-4 font-bold ${tone[c.status]}`} aria-hidden>{mark[c.status]}</span>
                  <span className="flex-1">
                    {c.check_name.replaceAll("_", " ")}
                    {c.status !== "pass" && c.reason && <span className="block text-xs text-muted">{c.reason}</span>}
                  </span>
                  <span className={`text-xs ${tone[c.status]}`}>{c.status.replace("_", " ")}</span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-1 font-semibold">Ledger</h2>
            <p className="mb-1.5 text-xs text-muted">
              Volume bookkeeping for the whole planned workflow, checked before any motion.
              {r.overall !== "pass" && r.failures[0]?.op_index !== undefined &&
                ` This run stopped at operation ${r.failures[0].op_index + 1}, so the planned values were never reached.`}
            </p>
            <table className="w-full rounded-md border border-rule bg-sheet text-left">
              <thead className="text-xs text-muted"><tr><th className="px-3 py-1 font-normal">Well</th><th className="text-right font-normal">Before</th><th className="px-3 text-right font-normal">After (planned)</th></tr></thead>
              <tbody>
                {Object.keys({ ...before, ...after }).map((k) => (
                  <tr key={k} className="border-t border-rule">
                    <td className="px-3 py-1">{k}</td>
                    <td className="text-right tabular-nums">{before[k] ?? "—"}</td>
                    <td className="px-3 text-right tabular-nums">{after[k] ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-xs">
            <dt className="text-muted">Simulator</dt><dd>{r.simulator_name} {r.simulator_version}</dd>
            <dt className="text-muted">Spec hash</dt><dd className="break-all">{r.experiment_spec_hash.slice(0, 16)}</dd>
            <dt className="text-muted">Scene hash</dt><dd className="break-all">{r.scene_hash.slice(0, 16)}</dd>
            <dt className="text-muted">Review</dt><dd>{r.review_state}</dd>
            <dt className="text-muted">Path</dt><dd>{r.path_length_mm.toFixed(0)} mm</dd>
          </dl>

          {run.graph_link && (
            <section className="rounded-md border border-rule bg-subtle px-3 py-2.5 text-xs">
              <h2 className="mb-1 text-sm font-semibold">How this run is linked</h2>
              <p>
                One link in the graph: this run <i>simulates a lab workflow (engineering only) for</i>{" "}
                {run.linked_entity?.label}. It is a computer prediction, unreviewed, and never counts as
                biological support: a pass cannot move any connection or ranking.
              </p>
              <p className="mt-1 text-muted">The workflow is a generic illustration, not a protocol for any real disease.</p>
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}

/** Ledger keys like source_ul / wells_ul.A1 become readable rows; values stay as recorded. */
function flatLedger(l: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(l)) {
    if (v && typeof v === "object") {
      for (const [w, x] of Object.entries(v as Record<string, number>)) out[`well ${w} (µL)`] = String(x);
    } else {
      const name = k.replace(/_ul$/, " (µL)").replaceAll("_", " ");
      out[name] = typeof v === "boolean" ? (v ? "yes" : "no") : String(v);
    }
  }
  return out;
}
