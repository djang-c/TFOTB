import Link from "next/link";
import { notFound } from "next/navigation";
import { safeHref } from "@/lib/safeHref";
import { api, ApiError, enc, type PatientGroups, type SourceCoverage, type AssetResult, type ConnectionResult, type CoverageManifest, type Entity, type GapResult } from "@/lib/api";
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
      api.groups(id).catch(() => null),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ApiDown what={id} />;
  }
  const [ent, conn, assets, gap, actions, graph, all, related, groups] = data;
  const groupList = groups?.status === "ok" ? groups.groups : [];
  // Similar-symptom diseases appear in Q1 once connections are computed; keep the other blocks.
  if (related && conn.results.length > 0) related.groups = related.groups.filter((g) => g.kind !== "phenotype_neighbours");
  const hasRelated = !!related && related.groups.length > 0;
  const e = ent.entity;
  const synthetic = e.source_type === "synthetic_fixture";
  // Real entries have no claims extracted from papers yet: one honest note instead of three empty sections.
  const noEvidence = !synthetic && conn.results.length === 0 && assets.assets.length === 0 && !gap.gap && actions.cards.length === 0;
  // A channel with no data for every candidate says nothing per row: state it once instead.
  // (Demo entries keep one well per channel, as docs/implementation/08 specifies.)
  const silent = conn.results.length > 0 && !synthetic
    ? [...new Set(conn.results.flatMap((r) => r.comparisons.map((c) => c.channel_id)))]
        .filter((ch) => conn.results.every((r) => r.comparisons.find((c) => c.channel_id === ch)?.availability === "missing"))
    : [];
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
        <div className="sticky top-20 text-sm">
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
        <p className="flex flex-wrap items-baseline gap-x-3 text-sm text-muted">
          <span className="capitalize">{e.type}</span>
          <span className="font-mono text-xs">{e.id}</span>
        </p>
        <h1 className="mt-0.5 text-[32px] leading-tight font-semibold tracking-tight">{e.label}</h1>
        {e.synonyms.length > 0 && <Synonyms names={e.synonyms} />}

        {!noEvidence && (
          <AtAGlance
            shares={conn.results}
            assets={assets.total ?? assets.assets.length}
            groups={groupList.length}
            openAssets={assets.assets.filter((a) => a.ranking_reasons.includes("open")).length}
            assetsFailed={assets.coverage?.status === "failed"}
            gap={gap.gap}
            actions={actions.cards.length}
          />
        )}


        {(synthetic || ent.summary.length > 0) && (
          <Section id="summary" title="Summary">
            <Summary sentences={ent.summary} attributes={e.attributes} />
            {ent.summary_method === "template" && (
              <p className="mt-2 text-xs text-muted">
                Written automatically from the records on this page; nothing is added or inferred. Sources:{" "}
                {[...new Set(ent.summary.map((x) => x.source).filter(Boolean))].join(" · ")}.
              </p>
            )}
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
              <>
              <p className="mb-3 text-sm text-muted">
                Each related disease shows what the two have in common. <b className="font-medium text-ink/80">Symptom overlap</b> runs
                from 0 (nothing in common) to 1 (the same recorded symptoms); it is a similarity, not a probability, and
                not a diagnosis. Labels such as &ldquo;symptom-level lead&rdquo; say how strong the evidence is, not how likely the link is.
              </p>
              {silent.length > 0 && (
                <p className="mb-3 text-sm text-muted">
                  {silent.map((c) => CHANNEL_LABEL[c] ?? c).join(", ")}: no data recorded for this entry in the indexed files, so
                  {silent.length === 1 ? " that channel is" : " those channels are"} left out below. Missing is not the same as no match.
                </p>
              )}
              <Reveal items={conn.results} first={5} noun="connections"
                render={(rs) => (
                  <ol className="divide-y divide-rule rounded-lg border border-rule">
                    {rs.map((r) => <ConnectionRow key={r.candidate_id} r={{ ...r, comparisons: r.comparisons.filter((c) => !silent.includes(c.channel_id)) }} label={labels[r.candidate_id] ?? r.candidate_id} labels={labels} note={conn.hierarchy?.[r.candidate_id]} />)}
                  </ol>
                )} />
              </>
            )}
          </Section>

          <Section id="existing" title="What useful work already exists?">
            {groups && groups.status !== "not_available" && groups.status !== "not_a_disease" && <PatientGroupsBlock g={groups} />}
            {assets.coverage && <SearchedLine c={assets.coverage} shown={assets.assets.length} total={assets.total ?? null} />}
            {assets.assets.length === 0 ? (
              <Empty>No registries, studies or models are linked to this entry yet.</Empty>
            ) : (
              <>
                <p className="mb-3 text-sm text-muted">Listed by practical fit (open first, then most recently updated), separately from the biology above.</p>
                <Reveal items={assets.assets} first={4} noun="studies and resources"
                  render={(xs) => <div className="divide-y divide-rule rounded-lg border border-rule">{xs.map((a) => <AssetRow key={a.asset_id} a={a} />)}</div>} />
                {assets.attribution && (
                  <p className="mt-3 text-xs text-muted">
                    Source: {assets.attribution}. Each record&apos;s last-update date on ClinicalTrials.gov is shown with it.
                    Our changes: {assets.modifications}
                  </p>
                )}
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
        <div className="mt-12 lg:hidden"><Infobox e={e} ent={ent} coverage={conn.coverage ?? gap.coverage} /></div>
      </article>

      <div className="hidden lg:block">
        <div className="sticky top-20"><Infobox e={e} ent={ent} coverage={conn.coverage ?? gap.coverage} /></div>
      </div>
    </main>
  );
}

const CHANNEL_LABEL: Record<string, string> = {
  phenotype: "Symptoms", dna: "DNA", rna: "RNA", mechanism: "Mechanism",
  dna_variants: "Shared gene", rna_effects: "RNA", molecular_mechanisms: "Mechanism", experimental_findings: "Experiments",
};

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-12 scroll-mt-20">
      <h2 className="mb-3 text-xl font-semibold tracking-tight">{title}</h2>
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
    <p className="max-w-[68ch] text-[17px] leading-relaxed">
      {sentences.map((s, i) => (
        <span key={i}>
          {s.text}
          {s.claim_ids.map((c) => <ClaimRef key={c} id={c} />)}{" "}
        </span>
      ))}
    </p>
  );
}

function ConnectionRow({ r, label, labels, note }: { r: ConnectionResult; label: string; labels: Record<string, string>; note?: string }) {
  return (
    <li className="grid gap-3 px-4 py-3.5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div>
        <Link href={`/entity/${enc(r.candidate_id)}`} className="font-semibold hover:text-link hover:underline hover:underline-offset-2">{label}</Link>
        {note && <p className="text-xs text-muted">{note[0].toUpperCase() + note.slice(1)}</p>}
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

function PatientGroupsBlock({ g }: { g: PatientGroups }) {
  if (g.status === "failed") return <p className="mb-6 text-sm text-ev-conflict">GARD could not be checked just now. This is not the same as no patient groups.</p>;
  if (g.status === "no_xref") return <p className="mb-6 text-sm text-muted">Patient groups: MONDO has no GARD cross-reference for this entry, so none could be looked up.</p>;
  return (
    <div className="mb-8">
      <h3 className="text-base font-semibold">Patient groups</h3>
      {g.groups.length === 0 ? (
        <p className="mt-1 text-sm text-muted">GARD lists no patient group for this disease. That may mean none exists yet, or that GARD has not recorded one.</p>
      ) : (
        <ul className="mt-2 divide-y divide-rule rounded-lg border border-rule">
          {g.groups.map((o) => (
            <li key={o.name} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 px-4 py-2.5 text-sm">
              <span>
                {safeHref(o.website) ? <a className="font-medium hover:text-link hover:underline" href={safeHref(o.website)} target="_blank" rel="noreferrer">{o.name}</a> : <span className="font-medium">{o.name}</span>}
                {o.country && <span className="ml-2 text-xs text-muted">{o.country}</span>}
              </span>
              {safeHref(o.registry_url) && <a className="ref text-xs" href={safeHref(o.registry_url)} target="_blank" rel="noreferrer">Patient registry</a>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted">
        {g.note} Retrieved {g.retrieved} from{" "}
        {g.pages.map((p, i) => <span key={p.url}>{i > 0 && ", "}{safeHref(p.url) ? <a className="ref" href={safeHref(p.url)} target="_blank" rel="noreferrer">GARD: {p.label}</a> : <span>GARD: {p.label}</span>}</span>)}.
      </p>
    </div>
  );
}

/** What a source search returned and how much survived the name check, from recorded counts. */
function SearchedLine({ c, shown, total }: { c: SourceCoverage; shown: number; total: number | null }) {
  if (c.status !== "ok") {
    return <p className="mb-3 text-sm text-ev-conflict">{c.source} could not be searched just now ({c.error ?? c.status}). This is not the same as no studies.</p>;
  }
  return (
    <p className="mb-3 text-sm text-muted">
      Searched {c.source} ({c.version}): {c.fetched} records returned, {c.screened} list this disease by name
      {c.fetched !== null && c.screened !== null && c.fetched > c.screened && "; the rest name related or broader conditions"}
      {total !== null && total > shown && `. Showing ${shown}`}.
    </p>
  );
}

function AssetRow({ a }: { a: AssetResult }) {
  const open = a.ranking_reasons.includes("open");
  const updated = a.ranking_reasons.find((r) => r.startsWith("last updated"));
  return (
    <details className="group px-4 py-3 [&_summary::-webkit-details-marker]:hidden">
      <summary className="cursor-pointer list-none">
        <span className="flex items-start justify-between gap-3">
          <span className="font-medium group-open:text-ink">{a.label}</span>
          {a.status && (
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${open ? "bg-ev-reviewed/10 text-ev-reviewed" : "bg-subtle text-muted"}`}>
              {a.status}
            </span>
          )}
        </span>
        <span className="mt-0.5 block text-xs text-muted">
          {[a.asset_kind.replaceAll("_", " "), a.reuse_limits[0], updated].filter(Boolean).join(" · ")}
          <span className="ml-2 text-link group-open:hidden">Details</span>
        </span>
      </summary>
      <dl className="mt-3 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[120px_1fr]">
        {a.status && (<><dt className="text-muted">Status</dt><dd>{a.status} <span className="text-muted">(checked {a.status_checked_at})</span></dd></>)}
        {a.access_conditions && (<><dt className="text-muted">Access</dt><dd>{a.access_conditions}</dd></>)}
        <dt className="text-muted">Why it fits</dt>
        <dd>{a.ranking_reasons.filter((r) => r !== "open").join(", ") || "not stated"} {a.relevance_claim_ids.map((c) => <ClaimRef key={c} id={c} />)}</dd>
        {a.reuse_limits.length > 0 && (<><dt className="text-muted">Differences</dt>
          <dd><ul className="list-disc pl-4">{a.reuse_limits.map((l) => <li key={l}>{l}</li>)}</ul></dd></>)}
        {a.needs_expert_review.length > 0 && (<><dt className="text-muted">Needs review</dt><dd>{a.needs_expert_review.join("; ")}</dd></>)}
        {a.contact && (<><dt className="text-muted">Record</dt><dd>{safeHref(a.contact.url) ? <a className="ref" href={safeHref(a.contact.url)} target="_blank" rel="noreferrer">{a.contact.label}</a> : a.contact.label}</dd></>)}
      </dl>
    </details>
  );
}

/** Shows the first few items; the rest sit behind one "Show all" disclosure. */
function Reveal<T>({ items, first, noun, render }: { items: T[]; first: number; noun: string; render: (xs: T[]) => React.ReactNode }) {
  if (items.length <= first + 1) return <>{render(items)}</>;
  return (
    <>
      {render(items.slice(0, first))}
      <details className="group mt-2 [&_summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none py-1 text-sm text-link hover:underline group-open:hidden">
          Show all {items.length} {noun}
        </summary>
        <div className="mt-2">{render(items.slice(first))}</div>
      </details>
    </>
  );
}

function Synonyms({ names }: { names: string[] }) {
  const shown = names.slice(0, 4);
  return (
    <div className="mt-1.5 text-sm text-muted">
      Also called {shown.join(" · ")}
      {names.length > shown.length && (
        <details className="inline [&_summary::-webkit-details-marker]:hidden">
          <summary className="ml-1 inline cursor-pointer list-none text-link hover:underline">+{names.length - shown.length} more</summary>
          <span> · {names.slice(shown.length).join(" · ")}</span>
        </details>
      )}
    </div>
  );
}

/** Summary first: the three questions, answered in one line each, linking to the detail below. */
function AtAGlance({ shares, assets, groups, openAssets, assetsFailed, gap, actions }: {
  shares: ConnectionResult[]; assets: number; groups: number; openAssets: number; assetsFailed: boolean; gap: GapResult | null; actions: number;
}) {
  const byCat = shares.reduce<Record<string, number>>((m, r) => ({ ...m, [r.category]: (m[r.category] ?? 0) + 1 }), {});
  const catLine = Object.entries(byCat).map(([c, n]) => `${n} ${c}`).join(" · ");
  const tiles = [
    { href: "#shares", q: "Who shares our characteristics?",
      a: shares.length ? `${shares.length} related ${shares.length === 1 ? "disease" : "diseases"}` : "None computed", sub: catLine || "No connection in the indexed evidence" },
    { href: "#existing", q: "What useful work already exists?",
      a: [groups ? `${groups} patient ${groups === 1 ? "group" : "groups"}` : "",
        assetsFailed ? "" : assets ? `${assets} ${assets === 1 ? "study" : "studies"}` : ""].filter(Boolean).join(" · ")
        || (assetsFailed ? "Source unavailable" : "None found"),
      sub: assetsFailed ? "Studies could not be checked; not the same as none" : assets ? `${openAssets} ${openAssets === 1 ? "study is" : "studies are"} open now` : "No study lists this disease by name" },
    { href: "#next", q: "What should we do next?",
      a: actions ? `${actions} drafted ${actions === 1 ? "step" : "steps"}` : gap ? "An open question" : "Not drafted yet",
      sub: gap ? (GAP_KIND[gap.kind] ?? gap.kind) : actions ? "Each needs review before use" : "Needs the evidence above to be reviewed" },
  ];
  return (
    <div className="mt-6 grid gap-px overflow-hidden rounded-lg border border-rule bg-rule sm:grid-cols-3">
      {tiles.map((t) => (
        <a key={t.href} href={t.href} className="bg-sheet px-4 py-3 transition-colors hover:bg-subtle">
          <span className="block text-xs text-muted">{t.q}</span>
          <span className="mt-1 block font-semibold">{t.a}</span>
          <span className="mt-0.5 block text-xs text-muted">{t.sub}</span>
        </a>
      ))}
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
                    {CHANNEL_LABEL[c.channel_id] ?? c.channel_id} {c.availability === "available" ? "✓" : "—"}
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
