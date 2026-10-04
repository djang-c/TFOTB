import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  BookOpen,
  Boxes,
  ChevronRight,
  Download,
  FileJson,
  FlaskConical,
  Network,
} from "lucide-react";
import { useMemo, type ReactNode } from "react";
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
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import type { Claim } from "@/lib/api";
import { cardToMarkdown } from "@/lib/cards";
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
import { isNotFound, useActions, useConnections, useEntity, useGap, useGraph } from "@/lib/queries";

export const Route = createFileRoute("/entity/$id")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Dossier — The Flight of the Buffalo" },
      {
        name: "description",
        content:
          "Everything recorded about one entry: related diseases, the claims and their sources, hypotheses, gaps and next steps.",
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
  return <Dossier key={id} id={id} />;
}

type Bucket = "mechanistic" | "literature" | "phenotype";
const BUCKETS: [Bucket, string][] = [
  ["mechanistic", "Mechanistic"],
  ["literature", "Literature-supported"],
  ["phenotype", "Symptoms"],
];
const MECHANISM_TYPES = new Set(["mechanism", "compartment", "chemical", "drug"]);

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

/** One block of the dossier. Blocks flow down two balanced columns, so neither column makes the page long. */
function Block({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`mb-6 break-inside-avoid overflow-hidden rounded-lg border border-border bg-card [&>section:last-child]:border-b-0 ${className}`}
    >
      {children}
    </div>
  );
}

function Dossier({ id }: { id: string }) {
  const navigate = useNavigate();
  const openClaim = useOpenClaim();
  const entityQ = useEntity(id);
  const graph = useGraph(id, 40); // used only to name and type the other end of each claim
  const conn = useConnections(id);
  const cardsQ = useActions(id);
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
    clean(labels.get(x) ?? data?.labels?.[x] ?? (x === id ? entity?.label : undefined) ?? x);
  const claims = useMemo(() => data?.claims ?? [], [data]);
  const findings = claims.filter((c) => !isHypothesis(c));
  const hypotheses = claims.filter(isHypothesis);
  const bucketOf = (c: Claim): Bucket => {
    const t = [types.get(c.subject_id), types.get(c.object_id)];
    if (t.includes("phenotype")) return "phenotype";
    if (claimKind(c) === "reviewed" || t.some((x) => x && MECHANISM_TYPES.has(x)))
      return "mechanistic";
    return "literature";
  };

  if (entityQ.isError && isNotFound(entityQ.error)) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <h1 className="text-2xl font-semibold">Entry not found</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          “{id}” is not in the catalogue. Use the search on the left.
        </p>
      </div>
    );
  }
  if (entityQ.isError)
    return (
      <p role="alert" className="p-10 text-center text-sm text-destructive">
        The entry could not be loaded. Check that the API is running.
      </p>
    );
  if (!entity || !data)
    return <p className="p-10 text-center text-sm text-muted-foreground">Loading…</p>;

  const cards = cardsQ.data?.cards ?? [];
  const gap = gapQ.data?.gap ?? null;
  const results = conn.data?.results ?? [];
  const byCategory = results.reduce<Record<string, number>>(
    (m, r) => ({ ...m, [r.category]: (m[r.category] ?? 0) + 1 }),
    {},
  );
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
    for (const s of data.summary) lines.push(s.text, "");
    if (results.length)
      lines.push(
        "## Related diseases",
        ...results.map(
          (r) => `- ${conn.data?.labels?.[r.candidate_id] ?? r.candidate_id}: ${r.category}`,
        ),
        "",
      );
    if (gap)
      lines.push(
        "## What is not known",
        gap.statement,
        ...gap.missing_information.map((m) => `- ${m}`),
        "",
      );
    lines.push(
      "## Recommended next steps",
      ...nextSteps.map((s) => `- ${s.text} _(${s.source})_`),
      "",
    );
    lines.push(
      "## Claims",
      ...claims.flatMap((c) => [
        `- ${labelOf(c.subject_id)} ${plain(c.predicate)} ${labelOf(c.object_id)} — ${KIND_LABEL[claimKind(c)]}; ${originLabel(c)} [${c.claim_id}](${c.source_url})`,
        `  > ${c.source_span}`,
      ]),
      "",
    );
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
          connections: results,
          cards,
          gap,
          summary: data.summary,
        },
        null,
        2,
      ),
      "application/json",
    );
  const open = (next: string) => void navigate({ to: "/entity/$id", params: { id: next } });

  const glance = [
    {
      value: conn.isPending ? "…" : results.length,
      label: "related diseases",
      sub: conn.isPending
        ? "loading"
        : Object.entries(byCategory)
            .map(([c, n]) => `${n} ${c}`)
            .join(" · ") || "none computed",
    },
    {
      value: findings.length,
      label: "claims from papers",
      sub: findings.length ? "each with its passage and source" : "none read yet",
    },
    {
      value: hypotheses.length,
      label: "hypotheses",
      sub: hypotheses.length ? "labelled, never counted as evidence" : "none",
    },
    {
      value: nextSteps.length,
      label: "next steps",
      sub: gap ? "includes an open question" : "from drafted cards",
    },
  ];

  return (
    <div className="px-5 py-8 lg:px-10">
      <header className="flex flex-col gap-4 border-b border-border pb-6 xl:flex-row xl:items-end">
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
            <p className="mt-1 max-w-4xl text-sm text-muted-foreground">
              Also: {entity.synonyms.slice(0, 6).join(", ")}
              {entity.synonyms.length > 6 ? ` +${entity.synonyms.length - 6}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 xl:ml-auto">
          <Button asChild variant="outline" size="sm">
            <Link to="/explorer" search={{ id }}>
              <Network />
              Show in graph
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/clusters" search={{ id }}>
              <Boxes />
              Clusters
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={exportMarkdown}>
            <Download />
            Markdown
          </Button>
          <Button variant="outline" size="sm" onClick={exportJson}>
            <FileJson />
            JSON
          </Button>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-2 gap-3 rounded-lg border border-border/60 bg-muted/30 p-5 md:grid-cols-4">
        {glance.map((g) => (
          <div key={g.label}>
            <div className="font-mono text-2xl font-semibold">{g.value}</div>
            <div className="text-xs font-medium">{g.label}</div>
            <div className="mt-0.5 text-[11px] leading-4 text-muted-foreground">{g.sub}</div>
          </div>
        ))}
      </div>

      <div className="mt-6 gap-6 xl:columns-2">
        {data.summary.length > 0 && (
          <Block>
            <section className="p-6">
              <h2 className="text-sm font-semibold">What is known</h2>
              <ul className="mt-3 space-y-2 text-sm leading-6">
                {data.summary.map((s, i) => (
                  <li key={i}>
                    {s.text}{" "}
                    {s.claim_ids.map((c) => (
                      <ClaimChip key={c} id={c} />
                    ))}
                  </li>
                ))}
              </ul>
              {data.summary_method === "template" && (
                <p className="mt-2 text-[10px] text-muted-foreground">
                  Written automatically from the records on this page; nothing is added or inferred.
                </p>
              )}
            </section>
          </Block>
        )}
        {data.papers && data.papers.length > 0 && (
          <Block>
            <TermPapers data={data} />
          </Block>
        )}
        {results.length > 0 && (
          <Block>
            <Connections id={id} onFocus={open} onRoute={() => {}} />
          </Block>
        )}
        {hypotheses.length > 0 && (
          <Block>
            <Hypotheses claims={hypotheses} labelOf={labelOf} />
          </Block>
        )}
        <Block>
          <section className="p-6">
            <h2 className="text-sm font-semibold">
              Evidence read from papers{" "}
              <span className="font-normal text-muted-foreground">· {findings.length}</span>
            </h2>
            {findings.length === 0 && (
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                No claim read from a paper mentions this entry yet. That is not the same as none: it
                may simply not have been read.
              </p>
            )}
            {BUCKETS.map(([b, label]) => {
              const list = findings.filter((c) => bucketOf(c) === b);
              if (!list.length) return null;
              return (
                <div key={b} className="mt-4">
                  <p className="section-kicker">
                    {label} · {list.length}
                  </p>
                  <div className="mt-2 space-y-2">
                    {list.map((c) => (
                      <Button
                        key={c.claim_id}
                        variant="outline"
                        onClick={() => openClaim(c.claim_id)}
                        className="h-auto w-full items-start justify-start gap-3 whitespace-normal p-3 text-left"
                      >
                        <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" />
                        <span className="min-w-0 flex-1">
                          <strong className="block text-xs leading-5">
                            {labelOf(c.subject_id)}{" "}
                            <span className="font-normal text-muted-foreground">
                              {plain(c.predicate)}
                            </span>{" "}
                            {labelOf(c.object_id)}
                          </strong>
                          <span className="mt-1 line-clamp-2 block text-xs font-normal leading-5 text-muted-foreground">
                            “{c.source_span}”
                          </span>
                          <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                            <span className={`evidence-badge evidence-${claimKind(c)}`}>
                              {KIND_LABEL[claimKind(c)]}
                            </span>
                            <span>{originLabel(c)}</span>
                          </span>
                        </span>
                        <ChevronRight className="mt-1 size-3.5 shrink-0" />
                      </Button>
                    ))}
                  </div>
                </div>
              );
            })}
          </section>
        </Block>
        {gap && (
          <Block>
            <GapCard gap={gap} coverage={gapQ.data?.coverage ?? null} />
          </Block>
        )}
        <Block>
          <section className="p-6">
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
                      <span className="text-[10px] text-muted-foreground">{s.source}</span>{" "}
                      {s.claims.slice(0, 3).map((cid) => (
                        <ClaimChip key={cid} id={cid} />
                      ))}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-3 text-xs text-muted-foreground">No next steps recorded.</p>
            )}
          </section>
        </Block>
        <CollapsibleBlock>
          <Collaborators id={id} />
        </CollapsibleBlock>
        <CollapsibleBlock>
          <PatientGroups id={id} />
        </CollapsibleBlock>
        <Block>
          <Cards id={id} />
        </Block>
        <p className="break-inside-avoid px-1 text-[10px] leading-5 text-muted-foreground">
          Provenance: {entity.source_type.replaceAll("_", " ")} · identity {entity.identity_status}
          {entity.retrieved_at ? ` · retrieved ${entity.retrieved_at}` : ""}. Related-disease
          labels:{" "}
          {Object.keys(byCategory).map((c) => (
            <span
              key={c}
              className={`evidence-badge mr-1 ${CATEGORY_CLASS[c as keyof typeof CATEGORY_CLASS]}`}
            >
              {c}
            </span>
          ))}
          Research-support content; not clinical guidance.
        </p>
      </div>
    </div>
  );
}

/** A block whose content may render nothing (no researchers, no patient groups): no empty frame is left behind. */
function CollapsibleBlock({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 break-inside-avoid overflow-hidden rounded-lg border border-border bg-card empty:hidden [&>section:last-child]:border-b-0">
      {children}
    </div>
  );
}
