import Link from "next/link";
import { notFound } from "next/navigation";
import { api, ApiError, enc, type AssetResult, type ConnectionResult, type CoverageManifest, type Entity, type GapResult } from "@/lib/api";
import { ActionCardView } from "@/components/ActionCardView";
import { ApiDown } from "@/components/ApiDown";
import { CategoryPill, GAP_KIND, ReviewBadge, SourceBadge, StatusMark } from "@/components/Badges";
import { ClaimRef } from "@/components/EvidenceDrawer";
import { GraphSection } from "@/components/GraphSection";
import { RelatedGroups } from "@/components/RelatedGroups";
import { Wells } from "@/components/Wells";

export default async function EntityPage(props: PageProps<"/entity/[id]">) {
  const id = decodeURIComponent((await props.params).id);
  let data;
  try {
    data = await Promise.all([
      api.entity(id), api.connections(id), api.assets(id), api.gap(id), api.actions(id), api.graph(id), api.entities(),
      api.related(id).catch(() => null),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ApiDown what={id} />;
  }
  const [ent, conn, assets, gap, actions, graph, all, related] = data;
  // Similar-symptom diseases appear in Q1 once connections are computed; keep the other blocks.
  if (related && conn.results.length > 0) related.groups = related.groups.filter((g) => g.kind !== "phenotype_neighbours");
  const hasRelated = !!related && related.groups.length > 0;
  const e = ent.entity;
  const synthetic = e.source_type === "synthetic_fixture";
  // Real entries have no claims extracted from papers yet: one honest note instead of three empty sections.
  const noEvidence = !synthetic && conn.results.length === 0 && assets.assets.length === 0 && !gap.gap && actions.cards.length === 0;
  const labels: Record<string, string> = { ...Object.fromEntries(all.items.map((x: Entity) => [x.id, x.label])), ...conn.labels };
  const sections = [
    ...(synthetic || ent.summary.length > 0 ? [["summary", "Summary"]] : []),
    ...(hasRelated ? [["related", "Connected in the source data"]] : []),
    ...(noEvidence ? [["evidence", "Evidence from papers"]] : [
      ["shares", "Who shares our characteristics?"],
      ["existing", "What useful work already exists?"],
      ["next", "What should we do next?"],
    ]),
    ...(graph.nodes.length > 0 ? [["graph", "Graph"]] : []),
    ...(ent.claims.length > 0 ? [["sources", "Sources"]] : []),
  ];

  return (
    <main className="mx-auto grid max-w-[1240px] gap-8 px-4 py-8 lg:grid-cols-[180px_minmax(0,1fr)_300px]">
      <nav aria-label="Contents" className="hidden lg:block">
        <div className="sticky top-6 text-sm">
          <h2 className="mb-2 font-semibold">Contents</h2>
          <ol className="space-y-1.5">
            {sections.map(([anchor, title]) => (
              <li key={anchor}><a className="ref" href={`#${anchor}`}>{title}</a></li>
            ))}
          </ol>
        </div>
      </nav>

      <article className="min-w-0">
        {synthetic && (
          <p className="mb-5 flex items-start gap-3 rounded-md border border-rule bg-subtle px-4 py-2.5 text-sm">
            <span aria-hidden className="tape mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full" />
            <span><b className="font-semibold">Synthetic demo entry.</b>{" "}
              <span className="text-muted">Placeholder names and quotes that show how the full journey works. No biological claim.</span></span>
          </p>
        )}
        <p className="text-sm capitalize text-muted">{e.type}</p>
        <h1 className="text-[34px] font-semibold leading-tight">{e.label}</h1>
        {e.synonyms.length > 0 && <p className="mt-1 text-muted">Also called {e.synonyms.join(", ")}</p>}

        <div className="lg:hidden"><Infobox e={e} ent={ent} coverage={conn.coverage ?? gap.coverage} /></div>

        {(synthetic || ent.summary.length > 0) && (
          <Section id="summary" title="Summary">
            <Summary sentences={ent.summary} attributes={e.attributes} />
          </Section>
        )}

        {hasRelated && (
          <Section id="related" title="Connected in the source data">
            <p className="-mt-1 text-sm text-muted">
              Read directly from the pinned public files. Unreviewed: each block names where it came from.
            </p>
            <RelatedGroups related={related!} />
          </Section>
        )}

        {noEvidence ? (
          <Section id="evidence" title="Evidence from papers">
            <Empty>
              No claims have been extracted from papers for this entry yet, so there are no evidence-qualified
              connections, reusable assets or next steps to show. What the public reference files record is
              listed above. Missing is not the same as none: this entry has simply not been read.
            </Empty>
          </Section>
        ) : (
          <>
          <Section id="shares" title="Who shares our characteristics?">
            {conn.results.length === 0 ? (
              <Empty>No connections are computed for this entry in the indexed evidence.</Empty>
            ) : (
              <ol className="divide-y divide-rule rounded-md border border-rule bg-white">
                {conn.results.map((r) => <ConnectionRow key={r.candidate_id} r={r} label={labels[r.candidate_id] ?? r.candidate_id} labels={labels} />)}
              </ol>
            )}
          </Section>

          <Section id="existing" title="What useful work already exists?">
            {assets.assets.length === 0 ? (
              <Empty>No registries, studies or models are linked to this entry yet.</Empty>
            ) : (
              <>
                <p className="mb-3 text-sm text-muted">Listed by practical fit (access, status, overlap), separately from the biology above.</p>
                <div className="space-y-3">{assets.assets.map((a) => <AssetRow key={a.asset_id} a={a} />)}</div>
              </>
            )}
          </Section>

          <Section id="next" title="What should we do next?">
            {gap.gap && <GapCard gap={gap.gap} coverage={gap.coverage} />}
            {actions.cards.length === 0 && !gap.gap && <Empty>No next step is drafted for this entry.</Empty>}
            <div className="mt-3 space-y-4">
              {actions.cards.map((c) => (
                <ActionCardView key={c.card_id} card={c}
                  simulationHref={c.kind === "simulation_report" ? `/simulation/${enc("SIM:syn-pass")}` : undefined} />
              ))}
            </div>
          </Section>
          </>
        )}

        {graph.nodes.length > 0 && (
          <Section id="graph" title="Graph">
            <GraphSection data={graph} focusId={e.id} />
          </Section>
        )}

        {ent.claims.length > 0 && <Section id="sources" title="Sources">
          <ol className="space-y-2 text-sm">
            {ent.claims.map((c) => (
              <li key={c.claim_id} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <ClaimRef id={c.claim_id} />
                <span className="text-[15px]">{c.source_span}</span>
                <SourceBadge type={c.source_type} />
                <ReviewBadge state={c.review_state} />
                <StatusMark status={c.status} />
              </li>
            ))}
          </ol>
        </Section>}
      </article>

      <div className="hidden lg:block">
        <div className="sticky top-6"><Infobox e={e} ent={ent} coverage={conn.coverage ?? gap.coverage} /></div>
      </div>
    </main>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-10 scroll-mt-6">
      <h2 className="mb-3 border-b border-rule pb-1 text-2xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border border-dashed border-rule px-4 py-3 text-muted">{children}</p>;
}

function Summary({ sentences, attributes }: { sentences: { text: string; claim_ids: string[] }[]; attributes: Record<string, unknown> }) {
  if (sentences.length === 0) {
    const missing = attributes.summary_missing as string | undefined;
    return <p className="text-muted">No plain-language summary is drafted for this entry. {missing}</p>;
  }
  return (
    <p className="max-w-[68ch] text-[18px] leading-relaxed">
      {sentences.map((s, i) => (
        <span key={i}>
          {s.text}
          {s.claim_ids.map((c) => <ClaimRef key={c} id={c} />)}{" "}
        </span>
      ))}
    </p>
  );
}

function ConnectionRow({ r, label, labels }: { r: ConnectionResult; label: string; labels: Record<string, string> }) {
  return (
    <li className="grid gap-3 px-4 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div>
        <Link href={`/entity/${enc(r.candidate_id)}`} className="ref text-lg font-semibold">{label}</Link>
        <div className="mt-1"><CategoryPill category={r.category} /></div>
        {r.compatibility_flags.map((f) => (
          <p key={f} className={`mt-2 text-sm ${f.startsWith("Opposite") || f.startsWith("symptoms") ? "font-medium text-ev-conflict" : "text-muted"}`}>
            {f}
          </p>
        ))}
      </div>
      <Wells comparisons={r.comparisons} labels={labels} />
    </li>
  );
}

function AssetRow({ a }: { a: AssetResult }) {
  return (
    <div className="rounded-md border border-rule bg-white px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">{a.label}</h3>
        <span className="text-xs text-muted">{a.asset_kind.replaceAll("_", " ")}</span>
      </div>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[130px_1fr]">
        {a.status && (<><dt className="text-muted">Status</dt><dd>{a.status} <span className="text-muted">(checked {a.status_checked_at})</span></dd></>)}
        {a.access_conditions && (<><dt className="text-muted">Access</dt><dd>{a.access_conditions}</dd></>)}
        <dt className="text-muted">Why it fits</dt>
        <dd>{a.ranking_reasons.join(", ") || "not stated"} {a.relevance_claim_ids.map((c) => <ClaimRef key={c} id={c} />)}</dd>
        <dt className="text-muted">Differences</dt>
        <dd><ul className="list-disc pl-4">{a.reuse_limits.map((l) => <li key={l}>{l}</li>)}</ul></dd>
        {a.needs_expert_review.length > 0 && (<><dt className="text-muted">Needs review</dt><dd>{a.needs_expert_review.join("; ")}</dd></>)}
        {a.contact && (<><dt className="text-muted">Contact</dt><dd><a className="ref" href={a.contact.url} target="_blank" rel="noreferrer">{a.contact.label}</a></dd></>)}
      </dl>
    </div>
  );
}


function GapCard({ gap, coverage }: { gap: GapResult; coverage: CoverageManifest | null }) {
  return (
    <div className="rounded-md border-2 border-ev-gap/60 bg-white">
      <div className="border-b border-rule px-4 py-3">
        <p className="text-sm font-semibold text-ev-gap">{GAP_KIND[gap.kind] ?? gap.kind}</p>
        <p className="mt-1 text-xl leading-snug">{gap.statement}</p>
      </div>
      <div className="grid gap-4 px-4 py-3 text-sm md:grid-cols-2">
        <div>
          <h3 className="font-semibold">What could change this</h3>
          <ul className="mt-1 list-disc pl-4">{gap.missing_information.map((m) => <li key={m}>{m}</li>)}</ul>
          <p className="mt-3"><span className="font-semibold">Who should review:</span> {gap.reviewer_role}</p>
          {gap.known_claim_ids.length > 0 && <p className="mt-2">What is known: {gap.known_claim_ids.map((c) => <ClaimRef key={c} id={c} />)}</p>}
        </div>
        {coverage && <CoverageTable coverage={coverage} />}
      </div>
      <p className="border-t border-rule px-4 py-2 text-xs text-muted">{gap.scope_note}</p>
    </div>
  );
}

function CoverageTable({ coverage }: { coverage: CoverageManifest }) {
  const status = { ok: "searched", failed: "failed", unavailable: "unavailable", not_queried: "not searched" };
  return (
    <div>
      <h3 className="font-semibold">What was searched</h3>
      <table className="mt-1 w-full text-left">
        <thead className="text-xs text-muted">
          <tr><th className="py-1 font-normal">Source</th><th className="font-normal">Result</th><th className="text-right font-normal">Found</th></tr>
        </thead>
        <tbody>
          {coverage.per_source.map((s) => (
            <tr key={s.source} className="border-t border-rule">
              <td className="py-1 pr-2">{s.source}</td>
              <td className={s.status === "ok" ? "" : "text-ev-conflict"}>{status[s.status]}</td>
              <td className="text-right">{s.fetched ?? <span className="text-muted">n/a</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-xs text-muted">Counts recorded by {coverage.generated_by}, {coverage.retrieved_at.slice(0, 10)}.</p>
    </div>
  );
}

function Infobox({ e, ent, coverage }: { e: Entity; ent: Awaited<ReturnType<typeof api.entity>>; coverage: CoverageManifest | null }) {
  const failed = coverage?.per_source.filter((s) => s.status !== "ok").length ?? 0;
  return (
    <aside className="mt-4 rounded-md border border-rule bg-white text-sm lg:mt-0">
      {e.source_type === "synthetic_fixture" && <div className="tape h-1.5 rounded-t-md" aria-hidden />}
      <div className="px-4 py-3">
        <h2 className="text-base font-semibold">{e.label}</h2>
        <dl className="mt-2 grid grid-cols-[96px_1fr] gap-y-1.5">
          <dt className="text-muted">ID</dt><dd className="break-all">{e.id}</dd>
          <dt className="text-muted">Type</dt><dd className="capitalize">{e.type}</dd>
          <dt className="text-muted">Identity</dt><dd>{e.identity_status}</dd>
          <dt className="text-muted">Source</dt><dd><SourceBadge type={e.source_type} /></dd>
          {e.retrieved_at && <><dt className="text-muted">Retrieved</dt><dd>{e.retrieved_at}</dd></>}
          {e.source_version && <><dt className="text-muted">Version</dt><dd className="break-words">{e.source_version}</dd></>}
          <dt className="text-muted">Claims</dt><dd>{ent.claims.length} ({ent.reviewed_claims} reviewed)</dd>
          {coverage && (
            <>
              <dt className="text-muted">Coverage</dt>
              <dd>
                {coverage.per_source.length} sources
                {failed > 0 && <span className="text-ev-conflict">, {failed} not searched or failed</span>}
              </dd>
              <dt className="text-muted">Channels</dt>
              <dd>
                {coverage.per_channel.map((c) => (
                  <span key={c.channel_id} className="mr-2 whitespace-nowrap">
                    {c.channel_id} {c.availability === "available" ? "✓" : "—"}
                  </span>
                ))}
              </dd>
            </>
          )}
          {Object.entries(e.attributes)
            .filter(([k]) => !k.startsWith("summary"))
            .map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k.replaceAll("_", " ")}</dt><dd className="break-words">{String(v)}</dd>
              </div>
            ))}
        </dl>
      </div>
    </aside>
  );
}
