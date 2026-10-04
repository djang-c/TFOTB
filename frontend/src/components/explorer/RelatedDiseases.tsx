import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Reveal } from "@/components/explorer/Common";
import type { ReasonKind, RelatedReason } from "@/lib/api";
import {
  clean,
  EVIDENCE_BADGE,
  plain,
  REASON_ORDER,
  REASON_SHORT,
  REASON_TITLE,
} from "@/lib/labels";
import { useRelatedDiseases } from "@/lib/queries";

/**
 * Every disease related to this one, listed once, with each reason and where it comes from: reference data (HPO,
 * MONDO), papers, a hypothesis in a paper, an AI hypothesis, or computed symptom similarity. When nothing links it,
 * it says so: "No similarities found".
 */
export function RelatedDiseases({ id }: { id: string }) {
  const q = useRelatedDiseases(id);
  const [only, setOnly] = useState<ReasonKind | null>(null);
  const d = q.data;
  if (d && !d.applies) return null;
  const rows = (d?.diseases ?? []).filter((r) => !only || r.kinds.includes(only));
  return (
    <section className="rounded-lg border border-border bg-card p-6" aria-label="Related diseases">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold">
          Related diseases{" "}
          <span className="font-normal text-muted-foreground">
            · {q.isPending ? "…" : (d?.total ?? 0)}
          </span>
        </h2>
        {d && !d.none && (
          <div
            className="flex flex-wrap gap-1.5 text-[11px]"
            role="group"
            aria-label="Filter by reason"
          >
            <Chip on={!only} onClick={() => setOnly(null)}>
              All {d.total}
            </Chip>
            {REASON_ORDER.filter((k) => d.counts[k]).map((k) => (
              <Chip key={k} on={only === k} onClick={() => setOnly(only === k ? null : k)}>
                {d.counts[k]} {REASON_SHORT[k]}
              </Chip>
            ))}
          </div>
        )}
      </div>

      {q.isPending && (
        <p className="mt-3 text-sm text-muted-foreground">
          Comparing against every disease in the reference files…
        </p>
      )}
      {q.isError && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          Related diseases could not be loaded.
        </p>
      )}
      {d?.none && (
        <div className="mt-4 rounded-md border border-dashed border-border p-4">
          <p className="text-sm font-semibold">No similarities found.</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{d.note}</p>
        </div>
      )}
      {d && !d.none && (
        <>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{d.note}</p>
          {d.ai && (
            <p className="mt-2 text-xs leading-5">
              <span className="evidence-badge evidence-hypothesis mr-1.5">AI</span>
              {d.ai.note}
            </p>
          )}
          <Reveal
            items={rows}
            first={10}
            noun="related diseases"
            render={(xs) => (
              <ul className="mt-4 divide-y divide-border border-y border-border">
                {xs.map((r) => (
                  <li
                    key={r.id}
                    className="grid gap-2 py-3 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-6"
                  >
                    <div className="min-w-0">
                      <Link
                        to="/entity/$id"
                        params={{ id: r.id }}
                        className="text-sm font-medium hover:text-primary hover:underline"
                      >
                        {clean(r.label)}
                      </Link>
                      <p className="font-mono text-[10px] text-muted-foreground">{r.id}</p>
                      {r.hierarchy && (
                        <p className="mt-0.5 text-[11px] text-muted-foreground">{r.hierarchy}</p>
                      )}
                    </div>
                    <ul className="space-y-1.5">
                      {r.reasons.map((x) => (
                        <Reason key={`${x.kind}-${x.key}`} r={x} />
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          />
        </>
      )}
    </section>
  );
}

function Reason({ r }: { r: RelatedReason }) {
  const badge = EVIDENCE_BADGE[r.evidence];
  const what =
    r.kind === "symptoms"
      ? `${r.score?.toFixed(2)} · shares ${(r.shared ?? []).join(", ")}`
      : r.kind === "paper_link" || r.kind === "ai_hypothesis"
        ? plain(r.label)
        : r.label;
  return (
    <li className="text-xs leading-5">
      <span className="font-medium">{REASON_TITLE[r.kind]}</span>
      <span className="text-muted-foreground">: {what}</span>{" "}
      <span className={`evidence-badge ${badge.cls}`}>{badge.text}</span>{" "}
      {r.claim_ids.slice(0, 3).map((c) => (
        <ClaimChip key={c} id={c} />
      ))}
      {(r.kind === "ai_hypothesis" || r.kind === "paper_link") && r.detail && (
        <span className="mt-0.5 block text-[11px] leading-4 text-muted-foreground">
          {r.kind === "ai_hypothesis" ? "AI reasoning: " : "Paper: "}“{r.detail}”
        </span>
      )}
      {r.kind === "ai_hypothesis" && r.derived_from && r.derived_from.length > 0 && (
        <span className="mt-0.5 block text-[11px] text-muted-foreground">
          Built from{" "}
          {r.derived_from.map((c) => (
            <ClaimChip key={c} id={c} />
          ))}
        </span>
      )}
    </li>
  );
}

function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-0.5 ${on ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary/50"}`}
    >
      {children}
    </button>
  );
}
