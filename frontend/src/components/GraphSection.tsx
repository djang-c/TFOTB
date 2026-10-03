"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { enc, type GraphData } from "@/lib/api";
import { ClaimRef } from "./EvidenceDrawer";

const Graph3D = dynamic(() => import("./Graph3D"), {
  ssr: false,
  loading: () => <div className="grid h-[460px] place-items-center text-sm text-muted">Loading 3D view</div>,
});

export const NODE_COLOR: Record<string, string> = {
  disease: "#0d7266",
  gene: "#2563b8",
  variant: "#2563b8",
  mechanism: "#6b6f9a",
  phenotype: "#8a96a3",
  drug: "#b07a12",
  organization: "#b23a62",
  asset: "#3d8b4f",
  study: "#3d8b4f",
};

export function GraphSection({ data, focusId }: { data: GraphData; focusId: string }) {
  const [view, setView] = useState<"3d" | "list">("3d");
  const labels = Object.fromEntries(data.nodes.map((n) => [n.id, n.label]));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-muted">
          {data.nodes.length} entries and {data.edges.length} sourced links within two steps.
          Drag to turn, click a node to open it, click a link for its evidence.
        </p>
        <div role="tablist" className="inline-flex rounded-md border border-rule bg-white p-0.5">
          {(["3d", "list"] as const).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
              className={`rounded px-3 py-1 ${view === v ? "bg-ink text-white" : "text-muted"}`}>
              {v === "3d" ? "3D" : "List"}
            </button>
          ))}
        </div>
      </div>
      {view === "3d" ? (
        <>
          <Graph3D data={data} focusId={focusId} />
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {Object.entries(NODE_COLOR).filter(([t]) => data.nodes.some((n) => n.type === t)).map(([t, c]) => (
              <li key={t} className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} />{t}
              </li>
            ))}
            <li>line: solid observed, faint predicted, purple inferred</li>
          </ul>
        </>
      ) : (
        <table className="w-full rounded-md border border-rule bg-white text-left text-sm">
          <tbody>
            {data.edges.map((e) => (
              <tr key={e.claim_id} className="border-t border-rule first:border-0">
                <td className="px-3 py-1.5"><Link className="ref" href={`/entity/${enc(e.source)}`}>{labels[e.source]}</Link></td>
                <td className="text-muted">{e.predicate.toLowerCase().replaceAll("_", " ")}</td>
                <td><Link className="ref" href={`/entity/${enc(e.target)}`}>{labels[e.target]}</Link></td>
                <td className="pr-3 text-right"><ClaimRef id={e.claim_id} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
