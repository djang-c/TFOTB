import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Boxes } from "lucide-react";
import { z } from "zod";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { api, type ClusterGroup } from "@/lib/api";
import { useFocusId } from "@/lib/focus";
import { CATEGORY_CLASS, clean, plain } from "@/lib/labels";
import { isLocalId } from "@/lib/localTerms";
import { useEntity, useStarters } from "@/lib/queries";

export const Route = createFileRoute("/clusters")({
  ssr: false,
  validateSearch: z.object({ id: z.string().optional().catch(undefined) }),
  head: () => ({ meta: [{ title: "Clusters — The Flight of the Buffalo" }] }),
  component: ClustersPage,
});

const KIND: Record<ClusterGroup["kind"], { title: (label: string) => string; why: string }> = {
  mechanism: {
    title: (l) => `Share an observed mechanism: ${l}`,
    why: "Published claims place both diseases on the same compartment and substance.",
  },
  gene: {
    title: (l) => `Share the gene ${l}`,
    why: "Both are linked to this gene. Gene level only: not variant-level evidence and not a shared cause.",
  },
  direct: {
    title: (l) => `Linked directly: ${plain(l)}`,
    why: "A stored claim links the two diseases directly. Relationships of this kind are recorded as hypotheses.",
  },
  symptoms: {
    title: () => "Similar recorded symptoms",
    why: "Symptom similarity of 0.4 or more (0 to 1). Similarity, not a shared cause, and not a probability.",
  },
};

function ClustersPage() {
  const { id } = Route.useSearch();
  const focus = useFocusId();
  const { items: starters } = useStarters();
  const target =
    id ??
    (focus && !isLocalId(focus) ? focus : undefined) ??
    starters.find((s) => s.type === "disease")?.id;
  const entity = useEntity(target ?? "");
  const q = useQuery({
    queryKey: ["entityClusters", target],
    queryFn: () => api.entityClusters(target ?? ""),
    enabled: !!target,
    retry: 1,
  });
  const all = useQuery({ queryKey: ["clusters"], queryFn: api.clusters, retry: 1 });
  const groups = q.data?.groups ?? [];
  const name = entity.data ? clean(entity.data.entity.label) : target;

  return (
    <div className="px-5 py-8 lg:px-10">
      <header className="border-b border-border pb-6">
        <p className="section-kicker">Clusters</p>
        <h1 className="mt-2 text-3xl font-semibold">
          {target ? <>Groups around {name}</> : "Clusters"}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          {q.data?.note ??
            "Each group is the diseases that share one named feature with this entry. Use the search on the left to choose another entry."}
        </p>
      </header>

      {!target && (
        <p className="mt-8 text-sm text-muted-foreground">
          Search for a disease on the left to see the groups it belongs to.
        </p>
      )}
      {q.isPending && target && <p className="mt-8 text-sm text-muted-foreground">Loading…</p>}
      {q.isError && (
        <p role="alert" className="mt-8 text-sm text-destructive">
          Clusters could not be loaded. Check that the API is running.
        </p>
      )}
      {q.data && groups.length === 0 && (
        <p className="mt-8 rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
          No group is computed for {name}. Groups come from its connections, which exist only for
          diseases. Missing is not the same as none: it may simply not have been read yet.
        </p>
      )}

      {groups.length > 0 && (
        <div className="mt-6 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {groups.map((g) => (
            <article
              key={`${g.kind}-${g.feature}`}
              className="flex flex-col rounded-lg border border-border bg-card p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-sm font-semibold leading-5">{KIND[g.kind].title(g.label)}</h2>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">
                  {g.members.length + 1} diseases
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{KIND[g.kind].why}</p>
              <ul className="mt-3 space-y-1.5">
                <li className="flex items-center gap-2 text-xs">
                  <span className="size-2 shrink-0 rounded-full bg-primary" />
                  <span className="font-medium">{name}</span>
                  <span className="text-[10px] text-muted-foreground">this entry</span>
                </li>
                {g.members.map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                    <span className="size-2 shrink-0 rounded-full entity-dot-disease" />
                    <Link
                      to="/clusters"
                      search={{ id: m.id }}
                      className="min-w-0 hover:text-primary hover:underline"
                    >
                      {clean(m.label)}
                    </Link>
                    {m.score !== undefined && (
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {m.score.toFixed(2)}
                      </span>
                    )}
                    <span className={`evidence-badge ${CATEGORY_CLASS[m.category]}`}>
                      {m.category}
                    </span>
                    {m.claim_ids.slice(0, 3).map((c) => (
                      <ClaimChip key={c} id={c} />
                    ))}
                    {m.shared && m.shared.length > 0 && (
                      <span className="w-full pl-4 text-[10px] text-muted-foreground">
                        shares {m.shared.join(", ")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}

      <section className="mt-12 border-t border-border pt-8">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Boxes className="size-4" />
          Every mechanism cluster in the stored papers
        </h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
          {all.data?.note ?? ""} Select a disease to see the groups around it.
        </p>
        {all.data && all.data.clusters.length === 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            No two diseases share an observed mechanism feature in the claims stored so far.
          </p>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {all.data?.clusters.map((c) => (
            <article
              key={c.diseases.map((d) => d.id).join("|")}
              className={`rounded-lg border p-5 ${c.diseases.some((d) => d.id === target) ? "border-primary/60 bg-accent/30" : "border-border bg-card"}`}
            >
              <p className="flex flex-wrap gap-1.5">
                {c.diseases.map((d) => (
                  <Link
                    key={d.id}
                    to="/clusters"
                    search={{ id: d.id }}
                    className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] hover:border-primary/50 hover:text-primary"
                  >
                    {clean(d.label)}
                  </Link>
                ))}
              </p>
              <ul className="mt-3 space-y-1.5 text-xs">
                {c.shared_features.map((f) => (
                  <li key={f.feature} className="flex flex-wrap items-center gap-1.5">
                    <b>{f.label}</b>{" "}
                    <span className="text-muted-foreground">
                      in {f.studies} {f.studies === 1 ? "study" : "studies"}
                    </span>
                    {f.claim_ids.slice(0, 3).map((id2) => (
                      <ClaimChip key={id2} id={id2} />
                    ))}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
