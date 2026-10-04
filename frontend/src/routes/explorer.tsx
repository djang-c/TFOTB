import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Copy,
  Download,
  Filter,
  Route as RouteIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { CatalogSearch } from "@/components/CatalogSearch";
import { cardToMarkdown } from "@/lib/cards";
import { LocalEntity } from "@/components/explorer/LocalEntity";
import { Hypotheses, GapCard, TermPapers } from "@/components/explorer/Overview";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { LookupPanel } from "@/components/LookupPanel";
import { Markdown } from "@/components/Markdown";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api, type Claim, type GraphData } from "@/lib/api";
import { useOpenClaim } from "@/lib/drawerContext";
import {
  CATEGORY_CLASS,
  claimKind,
  clean,
  isHypothesis,
  KIND_LABEL,
  originLabel,
  plain,
} from "@/lib/labels";
import { isLocalId } from "@/lib/localTerms";
import {
  isNotFound,
  useActions,
  useAssets,
  useConnections,
  useEntity,
  useGap,
  useGraph,
  useStarters,
} from "@/lib/queries";

export const Route = createFileRoute("/explorer")({
  ssr: false,
  validateSearch: z.object({
    q: z.string().optional().catch(undefined),
    id: z.string().optional().catch(undefined),
  }),
  head: () => ({
    meta: [
      { title: "Entity Explorer — The Flight of the Buffalo" },
      {
        name: "description",
        content:
          "Explore evidence-backed links between rare diseases, genes, variants, phenotypes, mechanisms, and research assets.",
      },
    ],
  }),
  component: ExplorerPage,
});

const TYPES = [
  "all",
  "disease",
  "gene",
  "variant",
  "phenotype",
  "mechanism",
  "compartment",
  "chemical",
  "drug",
  "term",
] as const;
type Tab = "overview" | "cards" | "claims";

function ExplorerPage() {
  const { q, id } = Route.useSearch();
  const navigate = Route.useNavigate();
  const { items: starters, meta } = useStarters();
  const open = (next: string) => void navigate({ to: "/explorer", search: { id: next } });
  const center = id ?? starters[0]?.id;
  if (id && isLocalId(id))
    return <LocalEntity key={id} id={id} onOpen={open} onHome={() => void navigate({ to: "/" })} />;
  if (!id && q) return <ResolveQuery q={q} onOpen={open} />;
  if (!center) {
    return (
      <div className="mx-auto max-w-xl px-5 py-20 text-center">
        <h1 className="text-2xl font-semibold">Entity explorer</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {meta.isError
            ? "The API did not answer."
            : "Search a disease, gene, symptom or mechanism to see its evidence graph."}
        </p>
        <CatalogSearch className="mt-6 text-left" onSelect={(e) => open(e.id)} autoFocus />
      </div>
    );
  }
  return <ExplorerView key={center} centerId={center} />;
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
  const [maxNodes, setMaxNodes] = useState(40);
  const [type, setType] = useState<(typeof TYPES)[number]>("all");
  const [pathTarget, setPathTarget] = useState<{ id: string; label: string } | null>(null);
  const [copied, setCopied] = useState("");

  const graph = useGraph(centerId, maxNodes);
  const center = useEntity(centerId);
  const selected = useEntity(selectedId);
  const routes = useQuery({
    queryKey: ["routes", centerId, pathTarget?.id],
    queryFn: () => api.routes(centerId, pathTarget?.id ?? ""),
    enabled: !!pathTarget,
    retry: 0,
  });
  const pathClaims = routes.data?.paths[0]?.hops.flatMap((h) => h.claim_ids) ?? [];

  const labels = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((n) => [n.id, n.label])),
    [graph.data],
  );
  const labelOf = (id: string) =>
    clean(labels.get(id) ?? (id === centerId ? center.data?.entity.label : undefined) ?? id);
  const groups = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const n of graph.data?.nodes ?? []) {
      if (n.id !== selectedId && (type === "all" || n.type === type))
        m.set(n.type, [...(m.get(n.type) ?? []), n.id]);
    }
    return [...m.entries()];
  }, [graph.data, selectedId, type]);
  const focus = (next: string) => {
    setSelectedId(next);
    setPathTarget(null);
    void navigate({ to: "/explorer", search: { id: next } });
  };

  if (center.isError && isNotFound(center.error)) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <h1 className="text-xl font-semibold">No entry for “{centerId}”</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          It may have been removed, or the ID was mistyped.
        </p>
        <CatalogSearch className="mt-5 text-left" onSelect={(e) => focus(e.id)} autoFocus />
      </div>
    );
  }
  if (center.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The entry could not be loaded. Check that the API is running.
      </p>
    );

  const sel = selected.data?.entity;
  const selType = sel?.type ?? graph.data?.nodes.find((n) => n.id === selectedId)?.type ?? "term";
  const claims = selected.data?.claims ?? [];
  const copyCard = async (content: string, id: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(id);
      window.setTimeout(() => setCopied(""), 2000);
    } catch {
      setCopied("");
    }
  };
  const exportCard = (content: string, id: string) => {
    const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${id.replace(/[^a-z0-9-]/gi, "-")}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1440px] border-x border-border">
      <div className="border-b border-border px-5 py-5 lg:px-7">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
          <div>
            <div className="section-kicker">
              Knowledge graph / Live from the API
              {center.data ? ` · ${clean(center.data.entity.label)}` : ""}
            </div>
            <h1 className="mt-1 text-2xl font-semibold">Entity explorer</h1>
          </div>
          <CatalogSearch
            compact
            className="w-full max-w-xl xl:ml-auto"
            onSelect={(e) => focus(e.id)}
          />
        </div>
      </div>
      <div className="grid min-h-[680px] xl:grid-cols-[minmax(0,1fr)_380px] xl:items-start">
        <section
          className="relative h-[560px] min-w-0 border-b border-border xl:sticky xl:top-16 xl:h-[max(560px,calc(100vh-10rem))] xl:border-b-0 xl:border-r"
          aria-label="Evidence graph"
        >
          <div className="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-center gap-1.5">
            {TYPES.filter((t) => t === "all" || graph.data?.nodes.some((n) => n.type === t)).map(
              (t) => (
                <Button
                  key={t}
                  variant={type === t ? "default" : "outline"}
                  size="sm"
                  onClick={() => setType(t)}
                  className="h-7 rounded-full px-2.5 text-[10px] capitalize"
                >
                  {t}
                </Button>
              ),
            )}
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
              pathClaimIds={pathClaims}
              typeFilter={type}
              onSelect={setSelectedId}
              onEdgeSelect={openClaim}
            />
          )}
          <div className="absolute bottom-4 left-5 right-5 flex flex-wrap items-center gap-3 bg-background/90 text-[10px] text-muted-foreground">
            <Filter className="size-3" />
            {graph.data
              ? `${graph.data.nodes.length} nodes · ${graph.data.edges.length} links${graph.data.truncated ? ` · ${graph.data.omitted} omitted` : ""}`
              : "…"}
            <span>
              · solid = reviewed, dashed = unreviewed, purple = hypothesis, dotted = computed (no
              claim) · select a link for evidence
            </span>
          </div>
        </section>
        <aside className="min-w-0 bg-card" aria-label="Entity inspector">
          <div className="border-b border-border p-6">
            <span className={`entity-type entity-${selType}`}>{selType}</span>
            <h2 className="mt-4 text-2xl font-semibold">
              {clean(sel?.label ?? labelOf(selectedId))}
            </h2>
            <code className="mt-2 block break-all text-xs text-muted-foreground">{selectedId}</code>
            {sel && sel.synonyms.length > 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                Also: {sel.synonyms.slice(0, 5).join(", ")}
                {sel.synonyms.length > 5 ? ` +${sel.synonyms.length - 5}` : ""}
              </p>
            )}
            {selected.isError && !sel && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                No catalogue page for this node. It appears in claims read from papers.
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              {selectedId !== centerId && (
                <Button size="sm" variant="outline" onClick={() => focus(selectedId)}>
                  Recenter graph here <ArrowRight />
                </Button>
              )}
              {sel && (
                <Button size="sm" asChild>
                  <Link to="/entity/$id" params={{ id: selectedId }}>
                    Open dossier <ArrowRight />
                  </Link>
                </Button>
              )}
            </div>
          </div>
          <div
            role="tablist"
            aria-label="Entity inspector"
            className="grid grid-cols-3 border-b border-border"
          >
            {(
              [
                ["overview", "Overview"],
                ["cards", "Action Cards"],
                ["claims", "Claims & Evidence"],
              ] as [Tab, string][]
            ).map(([key, label]) => (
              <Button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                variant="ghost"
                className={`h-11 rounded-none border-b-2 px-1 text-[11px] sm:text-xs ${tab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
              >
                {label}
              </Button>
            ))}
          </div>
          <div
            role="tabpanel"
            aria-label={
              tab === "overview"
                ? "Overview"
                : tab === "cards"
                  ? "Action Cards"
                  : "Claims and Evidence"
            }
          >
            {tab === "overview" && (
              <Overview
                id={selectedId}
                centerId={centerId}
                claims={claims}
                data={selected.data}
                graph={graph.data}
                labelOf={labelOf}
                pathTarget={pathTarget}
                setPathTarget={setPathTarget}
                routes={routes.data}
                routesPending={routes.isFetching}
                groups={groups}
                onSelect={setSelectedId}
                onFocus={focus}
              />
            )}
            {tab === "cards" && (
              <CardsTab
                id={selectedId}
                copied={copied}
                copyCard={copyCard}
                exportCard={exportCard}
              />
            )}
            {tab === "claims" && (
              <ClaimsTab claims={claims} labelOf={labelOf} loading={selected.isPending} />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Overview({
  id,
  centerId,
  claims,
  data,
  graph,
  labelOf,
  pathTarget,
  setPathTarget,
  routes,
  routesPending,
  groups,
  onSelect,
  onFocus,
}: {
  id: string;
  centerId: string;
  claims: Claim[];
  data: ReturnType<typeof useEntity>["data"];
  graph: GraphData | undefined;
  labelOf: (id: string) => string;
  pathTarget: { id: string; label: string } | null;
  setPathTarget: (t: { id: string; label: string } | null) => void;
  routes: Awaited<ReturnType<typeof api.routes>> | undefined;
  routesPending: boolean;
  groups: [string, string[]][];
  onSelect: (id: string) => void;
  onFocus: (id: string) => void;
}) {
  const gap = useGap(id);
  const conn = useConnections(id);
  const openClaim = useOpenClaim();
  const hyp = claims.filter(isHypothesis);
  const top = (conn.data?.results ?? []).slice(0, 5);
  const names = conn.data?.labels ?? {};
  return (
    <>
      {data && data.summary.length > 0 && (
        <div className="border-b border-border p-6">
          <h3 className="text-sm font-semibold">What is known</h3>
          <ul className="mt-3 space-y-2 text-xs leading-5">
            {data.summary.map((s, i) => (
              <li key={i}>
                {s.text}{" "}
                {s.claim_ids.map((c) => (
                  <ClaimChip key={c} id={c} />
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data?.papers && data.papers.length > 0 && <TermPapers data={data} />}
      {top.length > 0 && (
        <div className="border-b border-border p-6">
          <h3 className="text-sm font-semibold">
            Related diseases{" "}
            <span className="font-normal text-muted-foreground">· {conn.data?.results.length}</span>
          </h3>
          <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
            Each label says how strong the evidence is, not how likely the link is. The dossier
            shows why.
          </p>
          <ul className="mt-3 space-y-1">
            {top.map((r) => (
              <li key={r.candidate_id} className="flex items-start justify-between gap-2">
                <Button
                  variant="ghost"
                  onClick={() => onSelect(r.candidate_id)}
                  onDoubleClick={() => onFocus(r.candidate_id)}
                  className="h-auto min-w-0 flex-1 justify-start whitespace-normal px-2 py-1.5 text-left text-sm font-normal"
                >
                  {clean(names[r.candidate_id] ?? labelOf(r.candidate_id))}
                </Button>
                <span className={`evidence-badge mt-1.5 shrink-0 ${CATEGORY_CLASS[r.category]}`}>
                  {r.category}
                </span>
              </li>
            ))}
          </ul>
          <Button variant="link" asChild className="mt-1 h-auto p-0 text-xs">
            <Link to="/entity/$id" params={{ id }}>
              All related diseases and routes in the dossier →
            </Link>
          </Button>
        </div>
      )}
      {hyp.length > 0 && <Hypotheses claims={hyp} labelOf={labelOf} />}
      {gap.data?.gap && <GapCard gap={gap.data.gap} coverage={gap.data.coverage} />}
      <div className="border-b border-border p-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <RouteIcon className="size-4" />
          Path explorer
        </h3>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Evidence path from {labelOf(centerId)}, through claims read from papers.
        </p>
        <div className="mt-3">
          <CatalogSearch compact onSelect={(e) => setPathTarget({ id: e.id, label: e.label })} />
        </div>
        {pathTarget && (
          <div className="mt-3 text-xs">
            <p className="text-muted-foreground">To {clean(pathTarget.label)}</p>
            {routesPending ? (
              <p className="mt-2 text-muted-foreground">Looking for a route…</p>
            ) : routes && routes.paths.length > 0 ? (
              <ol className="mt-2 space-y-3">
                {routes.paths.slice(0, 3).map((p, i) => (
                  <li key={i}>
                    <p className="font-medium">{p.nodes.map((n) => clean(n.label)).join(" → ")}</p>
                    {p.shared_feature_stops.length > 0 && (
                      <p className="text-muted-foreground">
                        Shared feature, not a causal step:{" "}
                        {p.shared_feature_stops.map((s) => clean(s.label)).join(", ")}
                      </p>
                    )}
                    {p.hypothesis_only && (
                      <p className="font-medium text-hypothesis">
                        This route rests on a hypothesis.
                      </p>
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
              </ol>
            ) : (
              <p className="mt-2 text-muted-foreground">
                {routes?.gap?.statement ?? "No evidence path in the stored claims."}
              </p>
            )}
          </div>
        )}
      </div>
      <div className="p-6">
        <h3 className="text-sm font-semibold">Related entities</h3>
        {groups.map(([t, ids]) => (
          <div key={t} className="mt-4">
            <p className="font-mono text-[10px] uppercase text-muted-foreground">
              {t} · {ids.length}
            </p>
            {ids.map((n) => (
              <Button
                key={n}
                variant="ghost"
                onClick={() => onSelect(n)}
                onDoubleClick={() => onFocus(n)}
                className="h-auto w-full justify-start gap-3 whitespace-normal px-2 py-2 text-left font-normal"
              >
                <span className={`size-2 shrink-0 rounded-full entity-dot-${t}`} />
                <span className="text-sm">{labelOf(n)}</span>
              </Button>
            ))}
          </div>
        ))}
        {graph && groups.length === 0 && (
          <p className="mt-3 text-xs text-muted-foreground">Nothing else is linked here yet.</p>
        )}
      </div>
    </>
  );
}

function CardsTab({
  id,
  copied,
  copyCard,
  exportCard,
}: {
  id: string;
  copied: string;
  copyCard: (c: string, id: string) => Promise<void>;
  exportCard: (c: string, id: string) => void;
}) {
  const cards = useActions(id);
  const assets = useAssets(id);
  const list = cards.data?.cards ?? [];
  return (
    <>
      <div className="border-b border-border p-6">
        <h3 className="text-sm font-semibold">Action cards</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {cards.isPending ? "Loading…" : `${list.length} linked research notes`}. A person should
          review a card before it is used or sent.
        </p>
      </div>
      {cards.isError && (
        <p role="alert" className="p-6 text-xs text-destructive">
          Action cards could not be loaded.
        </p>
      )}
      {!cards.isPending && list.length === 0 && (
        <p className="p-6 text-xs text-muted-foreground">No action cards linked to this entity.</p>
      )}
      {list.map((card) => {
        const md = card.body_markdown.replace(/^# .*\n/, "");
        const label = plain(card.kind);
        return (
          <article key={card.card_id} className="border-b border-border p-6">
            <div className="flex items-center justify-between gap-2">
              <span className="section-kicker text-primary">{card.kind.replaceAll("_", " ")}</span>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  title="Copy Markdown"
                  aria-label={`Copy ${label} Markdown`}
                  onClick={() => void copyCard(cardToMarkdown(card), card.card_id)}
                >
                  {copied === card.card_id ? <Check /> : <Copy />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Download Markdown"
                  aria-label={`Download ${label} Markdown`}
                  onClick={() => exportCard(cardToMarkdown(card), card.card_id)}
                >
                  <Download />
                </Button>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">For {card.audience}</p>
            {card.this_week && <p className="mt-3 text-xs font-medium">{card.this_week}</p>}
            <div className="mt-3">
              <Markdown md={md} />
            </div>
            <p className="mt-3 text-[10px] text-muted-foreground">
              Owner: {card.responsible_human} · {card.limitations.join("; ")}
            </p>
          </article>
        );
      })}
      {assets.data && assets.data.assets.length > 0 && (
        <div className="p-6">
          <h3 className="text-sm font-semibold">Reusable assets</h3>
          {assets.data.assets.slice(0, 8).map((a) => (
            <div key={a.asset_id} className="mt-3 text-xs">
              <strong className="block">{clean(a.label)}</strong>
              <span className="text-muted-foreground">
                {[a.asset_kind.replaceAll("_", " "), a.status, a.access_conditions]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function ClaimsTab({
  claims,
  labelOf,
  loading,
}: {
  claims: Claim[];
  labelOf: (id: string) => string;
  loading: boolean;
}) {
  const open = useOpenClaim();
  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Claims & evidence</h3>
        <span className="text-xs text-muted-foreground">
          {loading ? "…" : `${claims.length} claims`}
        </span>
      </div>
      <div className="space-y-2">
        {claims.map((c) => {
          const kind = claimKind(c);
          return (
            <Button
              key={c.claim_id}
              variant="outline"
              onClick={() => open(c.claim_id)}
              className="h-auto w-full items-start justify-start gap-3 whitespace-normal p-3 text-left"
            >
              <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <strong className="block text-xs leading-5">
                  {labelOf(c.subject_id)} · {plain(c.predicate)} · {labelOf(c.object_id)}
                </strong>
                <span className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className={`evidence-badge evidence-${kind}`}>{KIND_LABEL[kind]}</span>
                  <span>{originLabel(c)}</span>
                  <span className="font-mono">{c.claim_id}</span>
                </span>
              </span>
              <ChevronRight className="mt-1 size-3.5 shrink-0" />
            </Button>
          );
        })}
      </div>
      {!loading && claims.length === 0 && (
        <p className="text-xs leading-5 text-muted-foreground">
          No claim read from a paper mentions this entry yet. That is not the same as no connection:
          it may simply not have been read.
        </p>
      )}
    </div>
  );
}
