import { useQuery } from "@tanstack/react-query";
import { Route as RouteIcon } from "lucide-react";
import { useState } from "react";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api, type ConnectionResult } from "@/lib/api";
import { CATEGORY_CLASS, CATEGORY_HELP, CHANNEL_NAME, clean, humanize } from "@/lib/labels";
import { Empty, Reveal, Section } from "./Common";

/** Related diseases and how strong the evidence is. There is no combined score and no probability. */
export function Connections({
  id,
  onFocus,
  onRoute,
}: {
  id: string;
  onFocus: (id: string) => void;
  onRoute: (claimIds: string[]) => void;
}) {
  const q = useQuery({
    queryKey: ["connections", id],
    queryFn: () => api.connections(id),
    retry: 1,
  });
  if (q.isPending) return <p className="p-6 text-xs text-muted-foreground">Loading connections…</p>;
  if (q.isError)
    return (
      <p role="alert" className="p-6 text-xs text-destructive">
        Connections could not be loaded.
      </p>
    );
  const { results, labels = {}, hierarchy = {} } = q.data;
  if (results.length === 0)
    return (
      <div className="p-6">
        <Empty>
          No connections are computed for this entry in the indexed evidence. Missing is not the
          same as none: it may simply not have been read yet.
        </Empty>
      </div>
    );
  const counts = results.reduce<Record<string, number>>(
    (m, r) => ({ ...m, [r.category]: (m[r.category] ?? 0) + 1 }),
    {},
  );
  return (
    <>
      <Section title="Related diseases" count={results.length}>
        <p className="text-[11px] leading-4 text-muted-foreground">
          Each row says how strong the evidence is. “Symptom overlap” runs from 0 to 1; it is a
          similarity, not a probability and not a diagnosis. A label says how strong the evidence
          is, not how likely the link is.
        </p>
        <p className="mt-3 flex flex-wrap gap-1.5">
          {Object.entries(counts).map(([c, n]) => (
            <span
              key={c}
              className={`evidence-badge ${CATEGORY_CLASS[c as ConnectionResult["category"]]}`}
            >
              {n} {c}
            </span>
          ))}
        </p>
      </Section>
      <ol className="divide-y divide-border">
        <Reveal
          items={results}
          first={8}
          noun="connections"
          render={(xs) =>
            xs.map((r) => (
              <Row
                key={r.candidate_id}
                id={id}
                r={r}
                labels={labels}
                note={hierarchy[r.candidate_id]}
                onFocus={onFocus}
                onRoute={onRoute}
              />
            ))
          }
        />
      </ol>
    </>
  );
}

function Row({
  id,
  r,
  labels,
  note,
  onFocus,
  onRoute,
}: {
  id: string;
  r: ConnectionResult;
  labels: Record<string, string>;
  note: string | undefined;
  onFocus: (id: string) => void;
  onRoute: (claimIds: string[]) => void;
}) {
  const [showRoute, setShowRoute] = useState(false);
  const name = clean(labels[r.candidate_id] ?? r.candidate_id);
  const sub = (t: string) => humanize(t, (id) => clean(labels[id] ?? id));
  const silent = r.comparisons
    .filter((c) => c.availability === "missing")
    .map((c) => CHANNEL_NAME[c.channel_id] ?? c.channel_id);
  return (
    <li className="p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Button
            variant="link"
            className="h-auto whitespace-normal p-0 text-left text-sm font-semibold text-foreground"
            onClick={() => onFocus(r.candidate_id)}
          >
            {name}
          </Button>
          {note && (
            <p className="text-[10px] text-muted-foreground">
              {note[0]?.toUpperCase()}
              {note.slice(1)}
            </p>
          )}
        </div>
        <span
          className={`evidence-badge shrink-0 ${CATEGORY_CLASS[r.category]}`}
          title={CATEGORY_HELP[r.category]}
        >
          {r.category}
        </span>
      </div>
      <p className="mt-1 text-[10px] leading-4 text-muted-foreground">
        {CATEGORY_HELP[r.category]}
      </p>
      {r.compatibility_flags.map((f) => (
        <p
          key={f}
          className={`mt-2 text-xs ${/^(Opposite|symptoms)/.test(f) ? "font-medium text-conflict" : "text-muted-foreground"}`}
        >
          {f}
        </p>
      ))}
      <ul className="mt-3 space-y-1.5">
        {r.comparisons
          .filter((c) => c.availability !== "missing")
          .map((c) => {
            const refs = [...c.supporting_claim_ids, ...c.contradicting_claim_ids];
            const shared = c.score === null ? c.context_matches.map(sub) : [];
            return (
              <li key={c.channel_id} className="text-[11px] leading-4">
                <span className="font-semibold">{CHANNEL_NAME[c.channel_id] ?? c.channel_id}</span>{" "}
                {c.availability !== "available" ? (
                  <span className="text-conflict">
                    {c.availability === "failed" ? "source failed" : c.availability}
                  </span>
                ) : c.score !== null ? (
                  <span title={c.score_definition ?? ""}>
                    overlap {c.score.toFixed(2)}
                    {c.context_matches.length > 0 && (
                      <span className="text-muted-foreground">
                        {" "}
                        · shares {c.context_matches.slice(0, 2).map(sub).join(", ")}
                      </span>
                    )}
                  </span>
                ) : shared.length > 0 ? (
                  <span>
                    {shared[0]?.startsWith("directly") ? "" : "shares "}
                    {shared.slice(0, 3).join(", ")}
                    {shared.length > 3 ? ` +${shared.length - 3}` : ""}
                  </span>
                ) : (
                  <span className="text-muted-foreground">none in common</span>
                )}
                {refs.length > 0 && (
                  <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
                    {refs.slice(0, 4).map((x) => (
                      <ClaimChip key={x} id={x} />
                    ))}
                    {refs.length > 4 && (
                      <span className="text-[10px] text-muted-foreground">+{refs.length - 4}</span>
                    )}
                  </span>
                )}
              </li>
            );
          })}
      </ul>
      {silent.length > 0 && (
        <p className="mt-1.5 text-[10px] text-muted-foreground">
          No data recorded for: {[...new Set(silent)].join(", ")}. Missing is not the same as no
          match.
        </p>
      )}
      <div className="mt-2 flex gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-[11px]"
          onClick={() => setShowRoute(!showRoute)}
          aria-expanded={showRoute}
        >
          <RouteIcon /> {showRoute ? "Hide route" : "Show route"}
        </Button>
      </div>
      {showRoute && <RouteView from={id} to={r.candidate_id} onRoute={onRoute} />}
    </li>
  );
}

/** Routes through stored claims between two entries. A "shared feature" stop is a thing both diseases show, not a causal step. */
function RouteView({
  from,
  to,
  onRoute,
}: {
  from: string;
  to: string;
  onRoute: (claimIds: string[]) => void;
}) {
  const q = useQuery({
    queryKey: ["routes", from, to],
    queryFn: () => api.routes(from, to),
    retry: 0,
  });
  if (q.isPending)
    return <p className="mt-2 text-[11px] text-muted-foreground">Looking for a route…</p>;
  if (q.isError)
    return <p className="mt-2 text-[11px] text-destructive">Routes could not be loaded.</p>;
  const { paths, gap } = q.data;
  if (paths.length === 0)
    return (
      <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
        {gap?.statement ?? "No route through the stored claims."} Only claims read from papers are
        used here.
      </p>
    );
  return (
    <ol className="mt-2 space-y-3 border-l-2 border-primary/40 pl-3">
      {paths.slice(0, 3).map((p, i) => (
        <li key={i} className="text-[11px] leading-5">
          <p>{p.nodes.map((n) => clean(n.label)).join(" → ")}</p>
          {p.shared_feature_stops.length > 0 && (
            <p className="text-muted-foreground">
              Shared feature, not a causal step:{" "}
              {p.shared_feature_stops.map((s) => clean(s.label)).join(", ")}
            </p>
          )}
          {p.hypothesis_only && (
            <p className="font-medium text-hypothesis">This route rests on a hypothesis.</p>
          )}
          <span className="flex flex-wrap items-center gap-1">
            {p.hops
              .flatMap((h) => h.claim_ids)
              .map((c) => (
                <ClaimChip key={c} id={c} />
              ))}
            <Button
              variant="link"
              className="h-auto p-0 text-[10px]"
              onClick={() => onRoute(p.hops.flatMap((h) => h.claim_ids))}
            >
              highlight in graph
            </Button>
          </span>
        </li>
      ))}
    </ol>
  );
}
