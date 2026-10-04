import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api, type Claim, type CoverageManifest, type GapResult } from "@/lib/api";
import {
  clean,
  doiOf,
  GAP_KIND,
  isDrugClaim,
  isHypothesis,
  originLabel,
  plain,
} from "@/lib/labels";
import { safeHref } from "@/lib/safeHref";
import { Empty, Reveal, Section } from "./Common";

type EntityData = Awaited<ReturnType<typeof api.entity>>;

export function Overview({
  id,
  data,
  labelOf,
  onSelect,
}: {
  id: string;
  data: EntityData;
  labelOf: (id: string) => string;
  onSelect: (id: string) => void;
}) {
  const gap = useQuery({ queryKey: ["gap", id], queryFn: () => api.gap(id), retry: 1 });
  const related = useQuery({ queryKey: ["related", id], queryFn: () => api.related(id), retry: 0 });
  const e = data.entity;
  const attrs = Object.entries(e.attributes).filter(([k]) => !k.startsWith("summary"));
  const hyp = data.claims.filter(isHypothesis);
  return (
    <>
      {e.source_type === "synthetic_fixture" && (
        <p className="border-b border-border bg-accent/40 p-4 text-xs">
          <b>Synthetic demo entry.</b> Placeholder names and quotes that show how the product works.
          No biological claim.
        </p>
      )}
      {data.summary.length > 0 && (
        <Section title="What is known">
          <ul className="space-y-2 text-xs leading-5">
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
        </Section>
      )}
      {attrs.length > 0 && (
        <Section title="Record">
          <dl className="grid grid-cols-[96px_1fr] gap-y-1.5 text-xs">
            {attrs.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground capitalize">{k.replaceAll("_", " ")}</dt>
                <dd className="break-words">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}
      {data.papers && data.papers.length > 0 && <TermPapers data={data} />}
      {hyp.length > 0 && <Hypotheses claims={hyp} labelOf={labelOf} />}
      {gap.data?.gap && <GapCard gap={gap.data.gap} coverage={gap.data.coverage} />}
      <Collaborators id={id} />
      <PatientGroups id={id} />
      {related.data && related.data.groups.length > 0 && (
        <Section title="Connected in the source data">
          <p className="-mt-1 mb-2 text-[11px] text-muted-foreground">
            Read from the pinned public files. Select one to inspect it; each block names its
            source.
          </p>
          {related.data.groups.map((g) => (
            <div key={g.kind} className="mt-4 first:mt-0">
              <p className="flex items-baseline justify-between font-mono text-[10px] uppercase text-muted-foreground">
                <span>{g.title}</span>
                <span>
                  {g.items.length < g.total ? `${g.items.length} of ${g.total}` : g.total}
                </span>
              </p>
              <p className="text-[10px] text-muted-foreground">Source: {g.source}</p>
              <Reveal
                items={g.items}
                first={5}
                noun={g.title.toLowerCase()}
                render={(xs) =>
                  xs.map((it) => (
                    <Button
                      key={it.id}
                      variant="ghost"
                      onClick={() => onSelect(it.id)}
                      className="h-auto w-full justify-start gap-3 whitespace-normal px-2 py-1.5 text-left font-normal"
                    >
                      <span className={`size-2 shrink-0 rounded-full entity-dot-${it.type}`} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs">{clean(it.label)}</span>
                        {(it.score != null || (it.shared?.length ?? 0) > 0) && (
                          <span className="block text-[10px] text-muted-foreground">
                            {it.score != null && `symptom overlap ${it.score.toFixed(2)}`}
                            {it.shared &&
                              it.shared.length > 0 &&
                              ` · shares ${it.shared
                                .slice(0, 3)
                                .map((s) => s.replace(/^HP:\d+\s*/, ""))
                                .join(", ")}`}
                          </span>
                        )}
                      </span>
                    </Button>
                  ))
                }
              />
            </div>
          ))}
        </Section>
      )}
    </>
  );
}

function TermPapers({ data }: { data: EntityData }) {
  return (
    <Section title="Papers that name it" count={data.papers?.length}>
      <p className="mb-3 text-[11px] leading-4 text-muted-foreground">
        PubMed-indexed journal articles found when this term was checked. Citations are copied from
        each paper's own record. No claim has been read from them yet.
      </p>
      <ul className="space-y-2 text-xs leading-5">
        {data.papers?.map((p) => (
          <li key={p.pmid}>
            {safeHref(p.url) ? (
              <a
                className="underline-offset-2 hover:underline"
                href={safeHref(p.url)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {p.title} <ExternalLink className="inline size-3" />
              </a>
            ) : (
              p.title
            )}
            <span className="block text-[10px] text-muted-foreground">
              {p.journal} · {p.year}
              {p.doi ? ` · DOI ${p.doi}` : ""} · PMID {p.pmid}
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** AI hypotheses and treatment ideas: always labelled, with the reasoning, the source and the claims they rest on. */
function Hypotheses({ claims, labelOf }: { claims: Claim[]; labelOf: (id: string) => string }) {
  const drugs = claims.filter(isDrugClaim);
  return (
    <Section
      title={drugs.length ? "Hypotheses and treatment ideas" : "Hypotheses"}
      count={claims.length}
      tone="bg-hypothesis/5"
    >
      <p className="mb-3 text-[11px] leading-4 text-muted-foreground">
        Not findings.{" "}
        {drugs.length > 0 &&
          "A treatment idea is something to discuss with experts, never advice or a recommendation to treat anyone. "}
        Each shows who proposed it, its reasoning and where to check it.
      </p>
      <ul className="space-y-3">
        {claims.map((c) => {
          const href = safeHref(c.source_url);
          return (
            <li
              key={c.claim_id}
              className="rounded-md border border-hypothesis/40 bg-background p-3 text-xs"
            >
              <p className="font-semibold leading-5">
                {labelOf(c.subject_id)}{" "}
                <span className="font-normal text-muted-foreground">{plain(c.predicate)}</span>{" "}
                {labelOf(c.object_id)}
              </p>
              <p className="mt-1.5 flex flex-wrap gap-1.5">
                <span className="evidence-badge evidence-hypothesis">{originLabel(c)}</span>
                <span className="evidence-badge">
                  {c.review_state === "reviewed" ? "reviewed" : "unreviewed"}
                </span>
              </p>
              <p className="mt-2 leading-5">
                <span className="text-muted-foreground">
                  {c.source_type === "ai_generated" ? "AI's reasoning: " : "Source passage: "}
                </span>
                {c.source_span.replace(/^AI hypothesis:\s*/, "")}
              </p>
              <p className="mt-2 flex flex-wrap items-center gap-1.5">
                <ClaimChip id={c.claim_id} />
                {c.derived_from.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    built from {c.derived_from.length} stored claims:
                  </span>
                )}
                {c.derived_from.slice(0, 4).map((d) => (
                  <ClaimChip key={d} id={d} />
                ))}
                {href && (
                  <a
                    className="ml-auto text-[10px] underline-offset-2 hover:underline"
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {doiOf(c.source_url) ? `DOI ${doiOf(c.source_url)}` : "source"}{" "}
                    <ExternalLink className="inline size-3" />
                  </a>
                )}
              </p>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

export function GapCard({ gap, coverage }: { gap: GapResult; coverage: CoverageManifest | null }) {
  return (
    <Section title="What is not known" tone="bg-accent/40">
      <span className="evidence-badge evidence-gap">
        {GAP_KIND[gap.kind] ?? gap.kind.replaceAll("_", " ")}
      </span>
      <p className="mt-3 text-sm leading-6">{gap.statement}</p>
      {gap.missing_information.length > 0 && (
        <>
          <p className="mt-3 text-xs font-semibold">What could change this</p>
          <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
            {gap.missing_information.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </>
      )}
      {coverage && coverage.per_source.length > 0 && (
        <table className="mt-3 w-full text-left text-[11px]">
          <caption className="mb-1 text-left text-xs font-semibold">What was searched</caption>
          <tbody>
            {coverage.per_source.map((s) => (
              <tr key={s.source} className="border-t border-border">
                <td className="py-1 pr-2">{s.source}</td>
                <td className={s.status === "ok" ? "" : "text-conflict"}>
                  {s.status === "ok" ? "searched" : s.status.replace("_", " ")}
                </td>
                <td className="text-right">{s.fetched ?? "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-3 text-[10px] leading-4 text-muted-foreground">
        As of {gap.as_of}. {gap.scope_note}
      </p>
    </Section>
  );
}

function Collaborators({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["collab", id], queryFn: () => api.collaborators(id), retry: 0 });
  const c = q.data;
  if (!c || c.items.length === 0) return null;
  return (
    <Section title="Researchers who published on this" count={c.total}>
      <p className="mb-3 text-[11px] leading-4 text-muted-foreground">
        From the {c.papers_considered} papers whose claims are stored.{" "}
        {c.bridges > 0
          ? `${c.bridges} also appear on papers about other diseases.`
          : "None appears on papers about other diseases we hold."}
      </p>
      <Reveal
        items={c.items}
        first={4}
        noun="people"
        render={(xs) => (
          <ul className="space-y-3 text-xs">
            {xs.map((i) => (
              <li key={`${i.name}-${i.orcid ?? ""}`}>
                <span className="font-medium">{i.name}</span>{" "}
                {i.orcid && safeHref(`https://orcid.org/${i.orcid}`) && (
                  <a
                    className="text-[10px] underline"
                    href={`https://orcid.org/${encodeURIComponent(i.orcid)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    ORCID
                  </a>
                )}{" "}
                <span className="text-[10px] text-muted-foreground">matched by {i.match}</span>
                {i.affiliation && (
                  <span className="block text-[10px] text-muted-foreground">{i.affiliation}</span>
                )}
                {i.papers.slice(0, 2).map((p) => (
                  <span key={p.source_id} className="block text-[11px]">
                    {safeHref(p.citation) ? (
                      <a
                        className="underline-offset-2 hover:underline"
                        href={safeHref(p.citation)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {p.title}
                      </a>
                    ) : (
                      p.title
                    )}
                  </span>
                ))}
                {i.also_studies.length > 0 && (
                  <span className="block text-[10px] text-muted-foreground">
                    Also on papers about {i.also_studies.map((a) => a.label).join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      />
      <p className="mt-3 text-[10px] leading-4 text-muted-foreground">{c.note}</p>
    </Section>
  );
}

function PatientGroups({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["groups", id], queryFn: () => api.groups(id), retry: 0 });
  const g = q.data;
  if (!g || g.status === "not_available" || g.status === "not_a_disease") return null;
  if (g.status === "failed")
    return (
      <Section title="Patient groups">
        <Empty>
          GARD could not be checked just now. That is not the same as no patient groups.
        </Empty>
      </Section>
    );
  if (g.status === "no_xref")
    return (
      <Section title="Patient groups">
        <Empty>MONDO has no GARD cross-reference for this entry, so none could be looked up.</Empty>
      </Section>
    );
  return (
    <Section title="Patient groups" count={g.groups.length}>
      {g.groups.length === 0 ? (
        <Empty>
          GARD lists no patient group for this disease. That may mean none exists yet or that GARD
          has not recorded one.
        </Empty>
      ) : (
        <ul className="space-y-2 text-xs">
          {g.groups.map((o) => (
            <li key={o.name}>
              {safeHref(o.website) ? (
                <a
                  className="font-medium underline-offset-2 hover:underline"
                  href={safeHref(o.website)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {o.name}
                </a>
              ) : (
                <span className="font-medium">{o.name}</span>
              )}
              {o.country && <span className="ml-2 text-muted-foreground">{o.country}</span>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[10px] leading-4 text-muted-foreground">
        {g.note} Listed by GARD (NIH), shown as recorded; not checked or endorsed here.
      </p>
    </Section>
  );
}
