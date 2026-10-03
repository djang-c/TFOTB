import Link from "next/link";
import { enc, type Related } from "@/lib/api";

// HPO association types in plain words. "Mendelian" = inherited through one gene.
const ASSOCIATION: Record<string, string> = {
  mendelian: "single-gene (Mendelian) link",
  polygenic: "one of several contributing genes",
  unknown: "link type not stated in the source",
};

/** Entries connected to one entry in the pinned files, one block per source. */
export function RelatedGroups({ related }: { related: Related }) {
  return (
    <>
      {related.groups.map((g) => (
        <div key={g.kind} className="mt-8">
          <h2 className="flex items-baseline justify-between gap-4 text-base font-semibold">
            {g.title}
            <span className="text-xs font-normal text-muted tabular-nums">
              {g.total > g.items.length ? `${g.items.length} of ${g.total}` : g.total}
            </span>
          </h2>
          <p className="mt-0.5 text-xs text-muted">Source: {g.source}</p>
          <ul className="mt-3 divide-y divide-rule rounded-lg border border-rule">
            {g.items.map((it) => (
              <li key={it.id}>
                <Link href={`/entity/${enc(it.id)}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-0.5 px-4 py-2.5 hover:bg-subtle">
                  <span className="truncate text-sm font-medium">{it.label}</span>
                  <span className="font-mono text-[11px] text-muted">{it.id}</span>
                  {(it.score != null || it.association) && (
                    <span className="col-span-2 text-xs text-muted">
                      {it.score != null && <>symptom overlap {it.score.toFixed(2)}</>}
                      {it.shared && it.shared.length > 0 && <> · shares {it.shared.map((s) => s.replace(/^HP:\d+\s*/, "")).join(", ")}</>}
                      {it.association && <>{ASSOCIATION[it.association] ?? `${it.association} association`} · record {it.source_id}</>}
                    </span>
                  )}
                </Link>
              </li>
          ))}
        </ul>
      </div>
      ))}
    </>
  );
}
