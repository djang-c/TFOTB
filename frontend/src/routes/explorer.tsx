import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Filter } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { CatalogSearch } from "@/components/CatalogSearch";
import { Claims } from "@/components/explorer/Claims";
import { Cards } from "@/components/explorer/Cards";
import { Connections } from "@/components/explorer/Connections";
import { LocalEntity } from "@/components/explorer/LocalEntity";
import { Overview } from "@/components/explorer/Overview";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { LookupPanel } from "@/components/LookupPanel";
import { useOpenClaim } from "@/lib/drawerContext";
import { Button } from "@/components/ui/button";
import { api, ApiError, type Claim, type GraphData } from "@/lib/api";
import { clean, plain } from "@/lib/labels";
import { isLocalId } from "@/lib/localTerms";

export const Route = createFileRoute("/explorer")({
  ssr: false,
  validateSearch: z.object({
    id: z.string().optional().catch(undefined),
    q: z.string().optional().catch(undefined),
  }),
  component: ExplorerPage,
});

type Tab = "overview" | "connections" | "cards" | "claims";
const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["connections", "Connections"],
  ["cards", "Action cards"],
  ["claims", "Claims & evidence"],
];

function ExplorerPage() {
  const { id, q } = Route.useSearch();
  const navigate = Route.useNavigate();
  const open = (next: string) => void navigate({ to: "/explorer", search: { id: next } });
  if (id && isLocalId(id))
    return <LocalEntity key={id} id={id} onOpen={open} onHome={() => void navigate({ to: "/" })} />;
  if (id) return <ExplorerView key={id} centerId={id} />;
  if (q) return <ResolveQuery q={q} onOpen={open} />;
  return <Start onOpen={open} />;
}

function Start({ onOpen }: { onOpen: (id: string) => void }) {
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 300_000, retry: 1 });
  const seeds = meta.data?.real?.seed ?? meta.data?.featured ?? [];
  return (
    <div className="mx-auto max-w-xl px-5 py-20 text-center">
      <h1 className="text-2xl font-semibold">Entity explorer</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Search a disease, gene, symptom or mechanism to see its evidence graph.
      </p>
      <CatalogSearch className="mt-6 text-left" onSelect={onOpen} autoFocus />
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {seeds.map((s) => (
          <Button
            key={s.id}
            variant="outline"
            size="sm"
            className="rounded-full text-xs font-normal"
            onClick={() => onOpen(s.id)}
          >
            {s.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

/** `?q=` from a link or a bookmark: open the best match, or offer to look the term up. */
function ResolveQuery({ q, onOpen }: { q: string; onOpen: (id: string) => void }) {
  const s = useQuery({ queryKey: ["search", q], queryFn: () => api.search(q), retry: 1 });
  const first = s.data?.results[0]?.id;
  useEffect(() => {
    if (first) onOpen(first);
  }, [first]); // eslint-disable-line react-hooks/exhaustive-deps
  if (s.isPending || first)
    return <p className="p-10 text-center text-sm text-muted-foreground">Looking up “{q}”…</p>;
  if (s.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The catalogue could not be searched. Check that the API is running.
      </p>
    );
  return (
    <div className="mx-auto max-w-md p-6">
      <div className="rounded-md border border-border">
        <LookupPanel term={q} onOpen={onOpen} onOpenLocal={(t) => onOpen(t.id)} />
      </div>
    </div>
  );
}

function ExplorerView({ centerId }: { centerId: string }) {
  const navigate = Route.useNavigate();
  const openClaim = useOpenClaim();
  const [selectedId, setSelectedId] = useState(centerId);
  const [tab, setTab] = useState<Tab>("overview");
  const [type, setType] = useState("all");
  const [maxNodes, setMaxNodes] = useState(40);
  const [routeClaims, setRouteClaims] = useState<string[]>([]);

  const graph = useQuery({
    queryKey: ["graph", centerId, maxNodes],
    queryFn: () => api.graph(centerId, maxNodes),
    retry: 1,
  });
  const center = useQuery({
    queryKey: ["entity", centerId],
    queryFn: () => api.entity(centerId),
    retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 1,
  });
  const selected = useQuery({
    queryKey: ["entity", selectedId],
    queryFn: () => api.entity(selectedId),
    retry: false,
  });
  const conn = useQuery({
    queryKey: ["connections", centerId],
    queryFn: () => api.connections(centerId),
    retry: 0,
  });

  const labels = useMemo(() => {
    const m = new Map<string, string>();
    for (const n of graph.data?.nodes ?? []) m.set(n.id, n.label);
    for (const [k, v] of Object.entries(conn.data?.labels ?? {})) if (!m.has(k)) m.set(k, v);
    return m;
  }, [graph.data, conn.data]);
  const labelOf = (id: string) =>
    clean(labels.get(id) ?? (id === centerId ? center.data?.entity.label : undefined) ?? id);

  const focus = (next: string) => void navigate({ to: "/explorer", search: { id: next } });
  const types = useMemo(
    () => ["all", ...new Set((graph.data?.nodes ?? []).map((n) => n.type))],
    [graph.data],
  );

  if (center.isError && center.error instanceof ApiError && center.error.status === 404) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <h1 className="text-xl font-semibold">No entry for “{centerId}”</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          It may have been removed, or the ID was mistyped.
        </p>
        <CatalogSearch className="mt-5 text-left" onSelect={focus} autoFocus />
      </div>
    );
  }
  if (center.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The entry could not be loaded. Check that the API is running.
      </p>
    );

  return (
    <div className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1440px] border-x border-border">
      <div className="border-b border-border px-5 py-5 lg:px-7">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
          <div>
            <div className="section-kicker">Knowledge graph · live from the API</div>
            <h1 className="mt-1 text-2xl font-semibold">
              {center.data ? clean(center.data.entity.label) : "Loading…"}
            </h1>
          </div>
          <CatalogSearch compact className="w-full max-w-xl xl:ml-auto" onSelect={focus} />
        </div>
      </div>
      <div className="grid min-h-[680px] xl:grid-cols-[minmax(0,1fr)_420px] xl:items-start">
        <section
          className="relative h-[560px] min-w-0 border-b border-border xl:sticky xl:top-16 xl:h-[max(560px,calc(100vh-10rem))] xl:border-b-0 xl:border-r"
          aria-label="Evidence graph"
        >
          <div className="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-center gap-1.5">
            {types.map((t) => (
              <Button
                key={t}
                variant={type === t ? "default" : "outline"}
                size="sm"
                onClick={() => setType(t)}
                className="h-7 rounded-full px-2.5 text-[10px] capitalize"
              >
                {t}
              </Button>
            ))}
            <span className="ml-auto flex items-center gap-1 bg-background/90 text-[11px] text-muted-foreground">
              Nodes{" "}
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
              The graph could not be loaded.
            </p>
          )}
          {graph.data && graph.data.nodes.length <= 1 && (
            <p className="absolute inset-x-8 top-24 z-10 text-center text-sm text-muted-foreground">
              No other entry is linked to this one in the stored evidence yet. Missing is not the
              same as none.
            </p>
          )}
          {graph.data && (
            <KnowledgeGraph
              nodes={graph.data.nodes}
              edges={graph.data.edges}
              centerId={centerId}
              selectedId={selectedId}
              pathClaimIds={routeClaims}
              typeFilter={type}
              onSelect={setSelectedId}
              onEdgeSelect={openClaim}
            />
          )}
          <div className="absolute bottom-4 left-5 right-5 flex flex-wrap items-center gap-3 bg-background/90 text-[10px] text-muted-foreground">
            <Filter className="size-3" />{" "}
            {graph.data
              ? `${graph.data.nodes.length} nodes · ${graph.data.edges.length} links${graph.data.truncated ? ` · ${graph.data.omitted} omitted` : ""}`
              : "…"}
            <Legend />
          </div>
        </section>
        <aside className="min-w-0 bg-card" aria-label="Entity inspector">
          <Header
            id={selectedId}
            centerId={centerId}
            data={selected.data}
            failed={selected.isError}
            labelOf={labelOf}
            graph={graph.data}
            onFocus={focus}
          />
          <div
            role="tablist"
            aria-label="Entity inspector tabs"
            className="grid grid-cols-4 border-b border-border"
          >
            {TABS.map(([key, label]) => (
              <Button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                variant="ghost"
                className={`h-11 rounded-none border-b-2 px-1 text-[11px] ${tab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
              >
                {label}
              </Button>
            ))}
          </div>
          <div role="tabpanel" aria-label={TABS.find(([k]) => k === tab)?.[1]}>
            {selected.isPending && <p className="p-6 text-xs text-muted-foreground">Loading…</p>}
            {selected.isError ? (
              <NodeOnly id={selectedId} labelOf={labelOf} graph={graph.data} />
            ) : (
              selected.data && (
                <>
                  {tab === "overview" && (
                    <Overview
                      id={selectedId}
                      data={selected.data}
                      labelOf={labelOf}
                      onSelect={focus}
                    />
                  )}
                  {tab === "connections" && (
                    <Connections id={selectedId} onFocus={focus} onRoute={setRouteClaims} />
                  )}
                  {tab === "cards" && <Cards id={selectedId} />}
                  {tab === "claims" && <Claims claims={selected.data.claims} labelOf={labelOf} />}
                </>
              )
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="flex items-center gap-1">
        <i className="inline-block h-0 w-4 border-t-2 border-[#5fa79c]" />
        reviewed
      </span>
      <span className="flex items-center gap-1">
        <i className="inline-block h-0 w-4 border-t-2 border-dashed border-[#9aa0aa]" />
        unreviewed
      </span>
      <span className="flex items-center gap-1">
        <i className="inline-block h-0 w-4 border-t-2 border-dashed border-[#8a63c9]" />
        hypothesis
      </span>
      <span className="flex items-center gap-1">
        <i className="inline-block h-0 w-4 border-t-2 border-dotted border-[#d5d8de]" />
        computed (no claim)
      </span>
      <span>select a link to open its evidence</span>
    </span>
  );
}

function Header({
  id,
  centerId,
  data,
  failed,
  labelOf,
  graph,
  onFocus,
}: {
  id: string;
  centerId: string;
  data: Awaited<ReturnType<typeof api.entity>> | undefined;
  failed: boolean;
  labelOf: (id: string) => string;
  graph: GraphData | undefined;
  onFocus: (id: string) => void;
}) {
  const node = graph?.nodes.find((n) => n.id === id);
  const e = data?.entity;
  const type = e?.type ?? node?.type ?? "term";
  return (
    <div className="border-b border-border p-6">
      <span className={`entity-type entity-${type}`}>{type}</span>
      <h2 className="mt-4 text-2xl font-semibold">{clean(e?.label ?? labelOf(id))}</h2>
      <code className="mt-2 block break-all text-xs text-muted-foreground">{id}</code>
      {e && e.synonyms.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Also: {e.synonyms.slice(0, 5).join(", ")}
          {e.synonyms.length > 5 ? ` +${e.synonyms.length - 5}` : ""}
        </p>
      )}
      {e && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          {e.source_type === "database_record"
            ? "Public reference record"
            : e.source_type === "synthetic_fixture"
              ? "Synthetic demo entry"
              : e.source_type}{" "}
          · {e.review_state}
        </p>
      )}
      {failed && !e && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          No catalogue page for this node. It appears in claims read from papers.
        </p>
      )}
      {id !== centerId && (
        <Button size="sm" variant="outline" className="mt-4" onClick={() => onFocus(id)}>
          Recenter graph here <ArrowRight />
        </Button>
      )}
    </div>
  );
}

/** A node that has no catalogue page (a cell compartment or a chemical named in a claim): list the claims that touch it. */
function NodeOnly({
  id,
  labelOf,
  graph,
}: {
  id: string;
  labelOf: (id: string) => string;
  graph: GraphData | undefined;
}) {
  const open = useOpenClaim();
  const edges = (graph?.edges ?? []).filter(
    (e) => (e.source === id || e.target === id) && e.claim_id,
  );
  return (
    <div className="p-6">
      <h3 className="text-sm font-semibold">Claims that mention it</h3>
      {edges.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">None in the current graph.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {edges.map((e) => (
            <li key={e.claim_id}>
              <Button
                variant="outline"
                className="h-auto w-full justify-start whitespace-normal py-2 text-left text-xs font-normal"
                onClick={() => open(e.claim_id ?? "")}
              >
                {labelOf(e.source)} · {plain(e.predicate)} · {labelOf(e.target)}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export type { Claim };
