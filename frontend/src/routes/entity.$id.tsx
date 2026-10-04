import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  BookOpen,
  ChevronRight,
  Download,
  FileJson,
  FlaskConical,
  Network,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Cards } from "@/components/explorer/Cards";
import { Connections } from "@/components/explorer/Connections";
import { LocalEntity } from "@/components/explorer/LocalEntity";
import {
  Collaborators,
  GapCard,
  Hypotheses,
  PatientGroups,
  TermPapers,
} from "@/components/explorer/Overview";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { Button } from "@/components/ui/button";
import type { Claim } from "@/lib/api";
import { useOpenClaim } from "@/lib/drawerContext";
import {
  claimKind,
  clean,
  GAP_KIND,
  isHypothesis,
  KIND_LABEL,
  originLabel,
  plain,
} from "@/lib/labels";
import { isLocalId } from "@/lib/localTerms";
import { isNotFound, useActions, useAssets, useEntity, useGap, useGraph } from "@/lib/queries";
import { cardToMarkdown } from "@/lib/cards";

export const Route = createFileRoute("/entity/$id")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Evidence dossier — The Flight of the Buffalo" },
      {
        name: "description",
        content:
          "Evidence dossier: neighborhood graph, claims with their sources, open gaps and recommended next steps.",
      },
    ],
  }),
  component: DossierRoute,
});

function DossierRoute() {
  const { id } = Route.useParams();
  const navigate = Route.useNavigate();
  if (isLocalId(id))
    return (
      <LocalEntity
        key={id}
        id={id}
        onOpen={(next) => void navigate({ to: "/entity/$id", params: { id: next } })}
        onHome={() => void navigate({ to: "/" })}
      />
    );
  return <DossierPage key={id} id={id} />;
}

type Bucket = "related" | "mechanistic" | "literature" | "phenotype" | "open";
const BUCKETS: [Bucket, string][] = [
  ["related", "Related diseases"],
  ["mechanistic", "Mechanistic leads"],
  ["literature", "Literature-supported"],
  ["phenotype", "Phenotypes / symptoms"],
  ["open", "Open hypotheses / gaps"],
];
const MECHANISM_TYPES = new Set(["mechanism", "compartment", "chemical", "drug"]);

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function EntityNotFound({ id }: { id: string }) {
  return (
    <div className="mx-auto max-w-xl px-6 py-24 text-center">
      <h1 className="text-2xl font-semibold">Entity not found</h1>
      <p className="mt-3 text-sm text-muted-foreground">“{id}” is not in the catalogue.</p>
      <Button asChild variant="outline" className="mt-6">
        <Link to="/explorer">Open the graph</Link>
      </Button>
    </div>
  );
}

function DossierPage({ id }: { id: string }) {
  const navigate = useNavigate();
  const openClaim = useOpenClaim();
  const entityQ = useEntity(id);
  const graph = useGraph(id, 24);
  const cardsQ = useActions(id);
  const assetsQ = useAssets(id);
  const gapQ = useGap(id);
  const data = entityQ.data;
  const entity = data?.entity;
  const types = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((n) => [n.id, n.type])),
    [graph.data],
  );
  const labels = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((n) => [n.id, n.label])),
    [graph.data],
  );
  const labelOf = (x: string) =>
    clean(labels.get(x) ?? (x === id ? entity?.label : undefined) ?? x);
  const claims = data?.claims ?? [];
  const bucketOf = (c: Claim): Bucket => {
    const kind = claimKind(c);
    if (kind === "hypothesis" || kind === "conflict") return "open";
    const t = [types.get(c.subject_id), types.get(c.object_id)];
    if (t.includes("phenotype")) return "phenotype";
    if (kind === "reviewed" || t.some((x) => x && MECHANISM_TYPES.has(x))) return "mechanistic";
    return "literature";
  };
  const byBucket = useMemo(
    () =>
      Object.fromEntries(
        BUCKETS.map(([b]) => [b, claims.filter((c) => bucketOf(c) === b)]),
      ) as Record<Bucket, Claim[]>,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [claims, types],
  );
  const isDisease = entity?.type === "disease";
  const [chosen, setBucket] = useState<Bucket | null>(null);
  const bucket: Bucket = chosen ?? (isDisease ? "related" : "mechanistic");

  if (entityQ.isError && isNotFound(entityQ.error)) return <EntityNotFound id={id} />;
  if (entityQ.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The entry could not be loaded. Check that the API is running.
      </p>
    );
  if (!entity || !data)
    return <p className="p-10 text-center text-sm text-muted-foreground">Loading…</p>;

  const cards = cardsQ.data?.cards ?? [];
  const assets = assetsQ.data?.assets ?? [];
  const gap = gapQ.data?.gap ?? null;
  const summary = data.summary;
  const nextSteps = [
    ...cards
      .filter((c) => c.this_week)
      .map((c) => ({ text: c.this_week, source: plain(c.kind), claims: c.claim_ids })),
    ...(gap?.missing_information ?? []).map((m) => ({
      text: `Resolve: ${m}`,
      source: "gap analysis",
      claims: gap?.known_claim_ids ?? [],
    })),
  ];
  const slug = id.replace(/[^a-z0-9-]/gi, "-");

  const exportMarkdown = () => {
    const lines = [
      `# ${clean(entity.label)} (${entity.id})`,
      `Type: ${entity.type} · Review: ${entity.review_state} · Exported ${new Date().toISOString().slice(0, 10)}`,
      "",
    ];
    for (const s of summary) lines.push(s.text, "");
    if (gap)
      lines.push("## Gap", gap.statement, ...gap.missing_information.map((m) => `- ${m}`), "");
    lines.push(
      "## Recommended next steps",
      ...nextSteps.map((s) => `- ${s.text} _(${s.source})_`),
      "",
    );
    for (const [b, label] of BUCKETS.filter(([k]) => k !== "related")) {
      lines.push(`## ${label}`);
      for (const c of byBucket[b])
        lines.push(
          `- ${labelOf(c.subject_id)} ${plain(c.predicate)} ${labelOf(c.object_id)} — ${KIND_LABEL[claimKind(c)]}; ${originLabel(c)} [${c.claim_id}](${c.source_url})`,
          `  > ${c.source_span}`,
        );
      lines.push("");
    }
    lines.push("## Action cards", ...cards.flatMap((c) => [cardToMarkdown(c), ""]));
    lines.push(
      "---",
      "Research-support content only. Not clinical guidance. Nothing here has been reviewed by an expert unless it says so.",
    );
    download(`${slug}-dossier.md`, lines.join("\n"), "text/markdown;charset=utf-8");
  };
  const exportJson = () =>
    download(
      `${slug}-provenance.json`,
      JSON.stringify(
        {
          exported_at: new Date().toISOString(),
          entity,
          claims,
          cards,
          assets,
          gap,
          summary,
          neighborhood: { nodes: graph.data?.nodes.map((n) => n.id), edges: graph.data?.edges },
        },
        null,
        2,
      ),
      "application/json",
    );
  const open = (next: string) => void navigate({ to: "/entity/$id", params: { id: next } });

  return (
    <div className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1440px] border-x border-border">
      <header className="border-b border-border px-5 py-6 lg:px-7">
        <Link
          to="/explorer"
          search={{ id }}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <ArrowLeft className="size-3" />
          Back to graph
        </Link>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`entity-type entity-${entity.type}`}>{entity.type}</span>
              <code className="text-xs text-muted-foreground">{entity.id}</code>
              <span className="evidence-badge">{entity.review_state}</span>
              {entity.source_type === "synthetic_fixture" && (
                <span className="evidence-badge">synthetic demo</span>
              )}
            </div>
            <h1 className="mt-3 text-3xl font-semibold">{clean(entity.label)}</h1>
            {entity.synonyms.length > 0 && (
              <p className="mt-1 text-sm text-muted-foreground">
                Also: {entity.synonyms.slice(0, 6).join(", ")}
                {entity.synonyms.length > 6 ? ` +${entity.synonyms.length - 6}` : ""}
              </p>
            )}
          </div>
          <div className="flex gap-2 lg:ml-auto">
            <Button variant="outline" size="sm" onClick={exportMarkdown}>
              <Download />
              Markdown summary
            </Button>
            <Button variant="outline" size="sm" onClick={exportJson}>
              <FileJson />
              JSON provenance
            </Button>
          </div>
        </div>
      </header>

      <div className="grid xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 border-b border-border xl:border-b-0 xl:border-r">
          <div className="relative h-[460px] border-b border-border">
            <div className="absolute left-4 top-4 z-10 flex items-center gap-2 bg-background/90 text-[11px] text-muted-foreground">
              <Network className="size-3.5" />
              {graph.data
                ? `Neighborhood · ${graph.data.nodes.length} nodes · ${graph.data.edges.length} links · select a node to open its dossier`
                : "Loading the neighborhood…"}
            </div>
            {graph.data && graph.data.nodes.length <= 1 && (
              <p className="absolute inset-x-8 top-16 z-10 text-center text-sm text-muted-foreground">
                No other entry is linked to this one in the stored evidence yet. Missing is not the
                same as none.
              </p>
            )}
            {graph.data && (
              <KnowledgeGraph
                nodes={graph.data.nodes}
                edges={graph.data.edges}
                centerId={id}
                selectedId={id}
                pathClaimIds={[]}
                typeFilter="all"
                onSelect={(n) => {
                  if (n !== id) open(n);
                }}
                onEdgeSelect={openClaim}
              />
            )}
          </div>
          <div
            role="tablist"
            aria-label="Evidence categories"
            className="flex overflow-x-auto border-b border-border"
          >
            {BUCKETS.filter(([b]) => b !== "related" || isDisease).map(([b, label]) => (
              <Button
                key={b}
                role="tab"
                aria-selected={bucket === b}
                variant="ghost"
                onClick={() => setBucket(b)}
                className={`h-11 shrink-0 rounded-none border-b-2 px-4 text-xs ${bucket === b ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
              >
                {label}{" "}
                {b !== "related" && (
                  <span className="ml-1 font-mono text-[10px]">{byBucket[b].length}</span>
                )}
              </Button>
            ))}
          </div>
          <div role="tabpanel" className={bucket === "related" ? "" : "space-y-2 p-5 lg:p-7"}>
            {bucket === "related" && <Connections id={id} onFocus={open} onRoute={() => {}} />}
            {bucket === "open" && gap && (
              <div className="mb-4 border-l-2 border-gap bg-accent/40 p-4">
                <span className="evidence-badge evidence-gap">
                  gap · {GAP_KIND[gap.kind] ?? gap.kind.replaceAll("_", " ")}
                </span>
                <p className="mt-2 text-sm leading-6">{gap.statement}</p>
                <ul className="mt-2 list-disc pl-4 text-xs text-muted-foreground">
                  {gap.missing_information.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            )}
            {bucket !== "related" &&
              byBucket[bucket].map((c) => (
                <Button
                  key={c.claim_id}
                  variant="outline"
                  onClick={() => openClaim(c.claim_id)}
                  className="h-auto w-full items-start justify-start gap-3 whitespace-normal p-4 text-left"
                >
                  <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <strong className="block text-sm leading-5">
                      {labelOf(c.subject_id)}{" "}
                      <span className="font-normal text-muted-foreground">
                        {plain(c.predicate)}
                      </span>{" "}
                      {labelOf(c.object_id)}
                    </strong>
                    <span className="mt-1.5 line-clamp-2 block text-xs font-normal leading-5 text-muted-foreground">
                      “{c.source_span.replace(/^AI hypothesis:\s*/, "")}”
                    </span>
                    <span className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                      <span className={`evidence-badge evidence-${claimKind(c)}`}>
                        {KIND_LABEL[claimKind(c)]}
                      </span>
                      <span>{originLabel(c)}</span>
                      <span className="font-mono">{c.claim_id}</span>
                      <span>· reviewed: {c.review_state === "reviewed" ? "yes" : "no"}</span>
                    </span>
                  </span>
                  <ChevronRight className="mt-1 size-3.5 shrink-0" />
                </Button>
              ))}
            {bucket !== "related" &&
              byBucket[bucket].length === 0 &&
              !(bucket === "open" && gap) && (
                <p className="text-xs text-muted-foreground">
                  No claims in this category. That is not the same as none exist: it may simply not
                  have been read yet.
                </p>
              )}
          </div>
        </section>

        <aside className="min-w-0 bg-card">
          {summary.length > 0 && (
            <div className="border-b border-border p-6">
              <h2 className="text-sm font-semibold">What is known</h2>
              <ul className="mt-3 space-y-2 text-xs leading-5">
                {summary.map((s, i) => (
                  <li key={i}>
                    {s.text}{" "}
                    {s.claim_ids.map((cid) => (
                      <Button
                        key={cid}
                        variant="link"
                        onClick={() => openClaim(cid)}
                        className="h-auto p-0 font-mono text-[10px]"
                      >
                        [{cid.replace("CLAIM:", "")}]
                      </Button>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.papers && data.papers.length > 0 && <TermPapers data={data} />}
          {claims.filter(isHypothesis).length > 0 && (
            <Hypotheses claims={claims.filter(isHypothesis)} labelOf={labelOf} />
          )}
          {gap && bucket !== "open" && <GapCard gap={gap} coverage={gapQ.data?.coverage ?? null} />}
          <div className="border-b border-border p-6">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <FlaskConical className="size-4" />
              Recommended next steps
            </h2>
            {nextSteps.length ? (
              <ol className="mt-3 space-y-3">
                {nextSteps.map((s, i) => (
                  <li key={i} className="flex gap-3 text-xs leading-5">
                    <span className="font-mono text-muted-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <span className="block">{s.text}</span>
                      <span className="text-[10px] text-muted-foreground">{s.source}</span>
                      {s.claims.slice(0, 3).map((cid) => (
                        <Button
                          key={cid}
                          variant="link"
                          onClick={() => openClaim(cid)}
                          className="ml-1 h-auto p-0 font-mono text-[10px]"
                        >
                          [{cid.replace("CLAIM:", "")}]
                        </Button>
                      ))}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-3 text-xs text-muted-foreground">No next steps recorded.</p>
            )}
          </div>
          <Collaborators id={id} />
          <PatientGroups id={id} />
          <Cards id={id} />
          <p className="p-6 text-[10px] leading-5 text-muted-foreground">
            Provenance: {entity.source_type.replaceAll("_", " ")} · identity{" "}
            {entity.identity_status}{" "}
            {entity.retrieved_at ? `· retrieved ${entity.retrieved_at}` : ""}. Research-support
            content; not clinical guidance.
          </p>
        </aside>
      </div>
    </div>
  );
}
