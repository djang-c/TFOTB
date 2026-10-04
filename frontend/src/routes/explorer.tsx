import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Crosshair, Filter, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { LocalEntity } from "@/components/explorer/LocalEntity";
import { LookupPanel } from "@/components/LookupPanel";
import { Button } from "@/components/ui/button";
import { api, type GraphEdge } from "@/lib/api";
import { useOpenClaim } from "@/lib/drawerContext";
import { useFocusId } from "@/lib/focus";
import { clean, plain } from "@/lib/labels";
import { isHypothesisEdge } from "@/lib/graphStyle";
import { isLocalId } from "@/lib/localTerms";
import { isNotFound, useEntity, useGraph, useStarters } from "@/lib/queries";

export const Route = createFileRoute("/explorer")({
  ssr: false,
  validateSearch: z.object({
    q: z.string().optional().catch(undefined),
    id: z.string().optional().catch(undefined),
  }),
  head: () => ({
    meta: [
      { title: "Graph — The Flight of the Buffalo" },
      {
        name: "description",
        content: "The evidence graph around an entry: every link is a claim you can open.",
      },
    ],
  }),
  component: GraphPage,
});

function GraphPage() {
  const { q, id } = Route.useSearch();
  const navigate = Route.useNavigate();
  const focus = useFocusId();
  const { items: starters } = useStarters();
  const open = (next: string) => void navigate({ to: "/explorer", search: { id: next } });
  const center = id ?? (focus && !isLocalId(focus) ? focus : undefined) ?? starters[0]?.id;
  if (id && isLocalId(id))
    return <LocalEntity key={id} id={id} onOpen={open} onHome={() => void navigate({ to: "/" })} />;
  if (!id && q) return <ResolveQuery q={q} onOpen={open} />;
  if (!center)
    return (
      <p className="p-10 text-center text-sm text-muted-foreground">
        Use the search on the left to choose what to graph.
      </p>
    );
  return <GraphView key={center} centerId={center} />;
}

/** `?q=` from a link or a bookmark: centre on the best match, or offer to look the term up. */
function ResolveQuery({ q, onOpen }: { q: string; onOpen: (id: string) => void }) {
  const s = useQuery({ queryKey: ["search", q], queryFn: () => api.search(q), retry: 1 });
  const first = s.data?.results[0]?.id;
  useEffect(() => {
    if (first) onOpen(first);
  }, [first]); // eslint-disable-line react-hooks/exhaustive-deps
  if (s.isPending || first)
    return <p className="p-10 text-center text-sm text-muted-foreground">Looking up “{q}”…</p>;
  return (
    <div className="mx-auto max-w-md p-6">
      <div className="rounded-md border border-border">
        <LookupPanel term={q} onOpen={onOpen} onOpenLocal={(t) => onOpen(t.id)} />
      </div>
    </div>
  );
}

const ORDER = [
  "disease",
  "gene",
  "phenotype",
  "mechanism",
  "compartment",
  "chemical",
  "drug",
  "variant",
  "term",
];

/** The graph, as big as the screen, with one small panel about the selected node: its links and the route to it. */
function GraphView({ centerId }: { centerId: string }) {
  const navigate = Route.useNavigate();
  const openClaim = useOpenClaim();
  const [selectedId, setSelectedId] = useState(centerId);
  const [maxNodes, setMaxNodes] = useState(40);
  const [type, setType] = useState("all");
  const [panel, setPanel] = useState(true);
  const graph = useGraph(centerId, maxNodes);
  const center = useEntity(centerId);
  const routes = useQuery({
    queryKey: ["routes", centerId, selectedId],
    queryFn: () => api.routes(centerId, selectedId),
    enabled: selectedId !== centerId,
    retry: 0,
  });
  const highlighted = routes.data?.paths[0]?.hops.flatMap((h) => h.claim_ids) ?? [];
  const nodes = useMemo(() => graph.data?.nodes ?? [], [graph.data]);
  const labels = useMemo(() => new Map(nodes.map((n) => [n.id, n.label])), [nodes]);
  const labelOf = (id: string) =>
    clean(labels.get(id) ?? (id === centerId ? center.data?.entity.label : undefined) ?? id);
  const types = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of nodes) counts.set(n.type, (counts.get(n.type) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]));
  }, [nodes]);
  const recenter = (id: string) => void navigate({ to: "/explorer", search: { id } });

  if (center.isError && isNotFound(center.error))
    return (
      <p className="p-10 text-center text-sm text-muted-foreground">
        No entry for “{centerId}”. Use the search on the left.
      </p>
    );

  return (
    <section
      className="relative h-[calc(100svh-6.25rem)] min-h-[560px] overflow-hidden bg-workspace"
      aria-label="Evidence graph"
    >
      {graph.isPending && (
        <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">
          Loading the graph…
        </p>
      )}
      {graph.isError && (
        <p
          role="alert"
          className="absolute inset-0 grid place-items-center px-8 text-center text-sm text-destructive"
        >
          The graph could not be loaded. Check that the API is running.
        </p>
      )}
      {graph.data && (
        <KnowledgeGraph
          nodes={graph.data.nodes}
          edges={graph.data.edges}
          centerId={centerId}
          selectedId={selectedId}
          pathClaimIds={highlighted}
          typeFilter={type}
          onSelect={(n) => {
            setSelectedId(n);
            setPanel(true);
          }}
          onEdgeSelect={openClaim}
        />
      )}

      <div className="pointer-events-none absolute inset-x-4 top-4 flex flex-col gap-2 md:right-[372px]">
        <div className="pointer-events-auto w-fit rounded-lg border border-border bg-background/95 px-4 py-3 shadow-sm">
          <p className="section-kicker">Graph centred on</p>
          <h1 className="mt-0.5 text-lg font-semibold leading-tight">
            {center.data ? clean(center.data.entity.label) : labelOf(centerId)}
          </h1>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {graph.data
              ? `${graph.data.nodes.length} nodes · ${graph.data.edges.length} links${graph.data.truncated ? ` · ${graph.data.omitted} more not shown` : ""}`
              : "…"}
          </p>
        </div>
        <div className="pointer-events-auto flex flex-wrap items-center gap-1.5">
          <Button
            variant={type === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setType("all")}
            className="h-7 rounded-full px-2.5 text-[10px]"
          >
            All
          </Button>
          {types.map(([t, n]) => (
            <Button
              key={t}
              variant={type === t ? "default" : "outline"}
              size="sm"
              onClick={() => setType(t)}
              className="h-7 rounded-full px-2.5 text-[10px] capitalize"
            >
              <span className={`size-1.5 rounded-full entity-dot-${t}`} />
              {t} <span className="font-mono opacity-70">{n}</span>
            </Button>
          ))}
          <span className="ml-2 flex items-center gap-1 rounded-full bg-background/90 px-2 text-[11px] text-muted-foreground">
            Nodes
            {[20, 40, 80].map((d) => (
              <Button
                key={d}
                size="sm"
                variant={maxNodes === d ? "secondary" : "outline"}
                onClick={() => setMaxNodes(d)}
                className="h-7 px-2 font-mono text-[10px]"
              >
                {d}
              </Button>
            ))}
          </span>
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 left-4 flex flex-wrap items-center gap-3 rounded-md bg-background/90 px-3 py-1.5 text-[10px] text-muted-foreground md:right-[372px]">
        <Filter className="size-3" />
        <Legend line="solid" color="#5fa79c" text="reviewed" />
        <Legend line="dashed" color="#9aa0aa" text="unreviewed" />
        <Legend line="dashed" color="#8a63c9" text="hypothesis" />
        <Legend line="dotted" color="#c4c8cf" text="computed (no claim)" />
        <span>Click a node to inspect it, a link to read its evidence. Drag to turn.</span>
      </div>

      {panel ? (
        <NodePanel
          id={selectedId}
          centerId={centerId}
          edges={graph.data?.edges ?? []}
          nodeType={nodes.find((n) => n.id === selectedId)?.type ?? "term"}
          labelOf={labelOf}
          routes={routes.data}
          routesPending={routes.isFetching}
          onSelect={setSelectedId}
          onRecenter={recenter}
          onClose={() => setPanel(false)}
        />
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="absolute right-4 top-4"
          onClick={() => setPanel(true)}
        >
          Show details
        </Button>
      )}
    </section>
  );
}

function Legend({
  line,
  color,
  text,
}: {
  line: "solid" | "dashed" | "dotted";
  color: string;
  text: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <i
        className="inline-block h-0 w-4 border-t-2"
        style={{ borderStyle: line, borderColor: color }}
      />
      {text}
    </span>
  );
}

function NodePanel({
  id,
  centerId,
  edges,
  nodeType,
  labelOf,
  routes,
  routesPending,
  onSelect,
  onRecenter,
  onClose,
}: {
  id: string;
  centerId: string;
  edges: GraphEdge[];
  nodeType: string;
  labelOf: (id: string) => string;
  routes: Awaited<ReturnType<typeof api.routes>> | undefined;
  routesPending: boolean;
  onSelect: (id: string) => void;
  onRecenter: (id: string) => void;
  onClose: () => void;
}) {
  const openClaim = useOpenClaim();
  const mine = edges.filter((e) => e.source === id || e.target === id);
  const byPredicate = new Map<string, GraphEdge[]>();
  for (const e of mine) byPredicate.set(e.predicate, [...(byPredicate.get(e.predicate) ?? []), e]);
  const sourced = mine.filter((e) => e.claim_id).length;
  return (
    <aside
      className="absolute inset-x-4 bottom-14 max-h-[45%] overflow-y-auto rounded-lg border border-border bg-background/95 p-5 shadow-lg md:inset-x-auto md:bottom-4 md:right-4 md:top-4 md:max-h-none md:w-[340px]"
      aria-label="Selected node"
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`entity-type entity-${nodeType}`}>{nodeType}</span>
        <Button
          variant="ghost"
          size="icon"
          className="-mr-2 -mt-2"
          onClick={onClose}
          aria-label="Hide details"
        >
          <X />
        </Button>
      </div>
      <h2 className="mt-3 text-lg font-semibold leading-snug">{labelOf(id)}</h2>
      <code className="mt-1 block break-all text-[11px] text-muted-foreground">{id}</code>
      {id !== centerId && (
        <Button size="sm" variant="outline" className="mt-3" onClick={() => onRecenter(id)}>
          <Crosshair /> Centre the graph here
        </Button>
      )}

      <h3 className="mt-5 text-xs font-semibold">
        Links in this view{" "}
        <span className="font-normal text-muted-foreground">
          · {mine.length} ({sourced} with a source)
        </span>
      </h3>
      {mine.length === 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          No link to this node is shown at this size.
        </p>
      )}
      <div className="mt-2 space-y-3">
        {[...byPredicate.entries()].map(([pred, list]) => (
          <div key={pred}>
            <p
              className={`text-[11px] ${list.some(isHypothesisEdge) ? "text-hypothesis" : "text-muted-foreground"}`}
            >
              {plain(pred)}
              {list.some(isHypothesisEdge) ? " · hypothesis" : ""}
            </p>
            <ul className="mt-1 space-y-1">
              {list.slice(0, 8).map((e) => {
                const other = e.source === id ? e.target : e.source;
                return (
                  <li
                    key={e.claim_id ?? `${e.source}|${e.target}|${e.predicate}`}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <button
                      className="min-w-0 truncate text-left hover:text-primary"
                      onClick={() => onSelect(other)}
                    >
                      {labelOf(other)}
                    </button>
                    {e.claim_id ? (
                      <ClaimChip id={e.claim_id} />
                    ) : (
                      <span className="shrink-0 text-[10px] text-muted-foreground">computed</span>
                    )}
                  </li>
                );
              })}
              {list.length > 8 && (
                <li className="text-[10px] text-muted-foreground">+{list.length - 8} more</li>
              )}
            </ul>
          </div>
        ))}
      </div>

      {id !== centerId && (
        <>
          <h3 className="mt-5 text-xs font-semibold">Route from {labelOf(centerId)}</h3>
          {routesPending ? (
            <p className="mt-2 text-xs text-muted-foreground">Looking for a route…</p>
          ) : routes && routes.paths.length > 0 ? (
            <ol className="mt-2 space-y-3 text-xs">
              {routes.paths.slice(0, 2).map((p, i) => (
                <li key={i} className="border-l-2 border-primary/40 pl-3">
                  <p className="font-medium leading-5">
                    {p.nodes.map((n) => clean(n.label)).join(" → ")}
                  </p>
                  {p.shared_feature_stops.length > 0 && (
                    <p className="text-muted-foreground">
                      Shared feature, not a causal step:{" "}
                      {p.shared_feature_stops.map((s) => clean(s.label)).join(", ")}
                    </p>
                  )}
                  {p.hypothesis_only && (
                    <p className="font-medium text-hypothesis">Rests on a hypothesis.</p>
                  )}
                  <span className="mt-1 flex flex-wrap gap-1">
                    {p.hops
                      .flatMap((h) => h.claim_ids)
                      .map((c) => (
                        <ClaimChip key={c} id={c} />
                      ))}
                  </span>
                </li>
              ))}
              <li className="text-[10px] text-muted-foreground">
                The first route is highlighted in blue.
              </li>
            </ol>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              {routes?.gap?.statement ?? "No route through claims read from papers."}
            </p>
          )}
        </>
      )}
      <p className="mt-5 flex items-center gap-1 text-[10px] text-muted-foreground">
        <ArrowRight className="size-3" /> Every link with a source opens its evidence.
      </p>
    </aside>
  );
}
