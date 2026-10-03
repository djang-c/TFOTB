import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { api, enc, type EntityType, type MatchKind, type Related, type SearchHit } from "@/lib/api";
import { ApiDown } from "@/components/ApiDown";
import { SearchBox } from "@/components/SearchBox";
import { RelatedGroups } from "@/components/RelatedGroups";

const MATCH_TEXT: Record<MatchKind, string> = {
  identifier: "identifier",
  label: "exact name",
  "exact synonym": "synonym",
  "related synonym": "related name",
  "all words": "contains every word",
  "close spelling": "close spelling",
  demo: "demo data",
};

const TYPE_GROUP: [EntityType, string][] = [
  ["disease", "Diseases"],
  ["gene", "Genes"],
  ["phenotype", "Symptoms"],
];

export default async function SearchPage(props: PageProps<"/search">) {
  const raw = (await props.searchParams).q;
  const q = (Array.isArray(raw) ? raw[0] : raw ?? "").trim();
  if (!q) {
    return (
      <main className="mx-auto max-w-[680px] px-4 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Search</h1>
        <div className="mt-6"><SearchBox size="lg" autoFocus /></div>
      </main>
    );
  }

  let res;
  try {
    res = await api.search(q);
  } catch {
    return <ApiDown what="search" />;
  }
  const hits = res.results;
  const onlyClose = hits.length > 0 && hits.every((h) => h.match === "close spelling");
  const ambiguous = !!res.ambiguous;
  const named = hits.filter((h) => h.match && ["label", "exact synonym", "related synonym", "identifier"].includes(h.match));
  const candidates = ambiguous ? named : [];
  const top = !ambiguous && !onlyClose ? hits[0] : undefined;
  const related: Related | null = top && top.source_type !== "synthetic_fixture"
    ? await api.related(top.id).catch(() => null)
    : null;
  const shown = new Set([top?.id, ...candidates.map((c) => c.id)]);
  const rest = hits.filter((h) => !shown.has(h.id));

  return (
    <main className="mx-auto max-w-[1240px] px-4 pt-10 pb-10">
      <p className="text-sm text-muted">Results for</p>
      <h1 className="text-[28px] font-semibold tracking-tight">{q}</h1>

      {hits.length === 0 && (
        <Notice>
          Nothing in the indexed sources matches “{q}”. Try another spelling, a synonym, a gene
          symbol (for example CLN3) or an identifier (for example MONDO:0018982).
        </Notice>
      )}
      {onlyClose && <Notice>No exact match for “{q}”. These are close spellings; pick the one you mean.</Notice>}
      {ambiguous && (
        <Notice>
          “{q}” is used by {candidates.length} different entries. They are kept apart, never
          merged: pick the one you mean.
        </Notice>
      )}

      <div className="mt-8 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-10">
          {top && (
            <section>
              <SectionLabel>Best match</SectionLabel>
              <MatchCard h={top} prominent />
              {related && <RelatedGroups related={related} />}
              {related && related.groups.length === 0 && (
                <p className="mt-6 rounded-lg border border-dashed border-rule px-4 py-3 text-sm text-muted">
                  No genes, similar diseases or annotated diseases are recorded for this entry in the indexed files.
                </p>
              )}
            </section>
          )}

          {(candidates.length > 0 || onlyClose) && (
            <section>
              <SectionLabel>{onlyClose ? "Did you mean" : "Which one do you mean?"}</SectionLabel>
              <div className="grid gap-3 sm:grid-cols-2">
                {(onlyClose ? hits : candidates).map((h) => <MatchCard key={h.id} h={h} />)}
              </div>
            </section>
          )}
        </div>

        {rest.length > 0 && !onlyClose && (
          <aside>
            <SectionLabel>Other matches</SectionLabel>
            <div className="space-y-6">
              {TYPE_GROUP.map(([t, name]) => {
                const items = rest.filter((h) => h.type === t);
                if (!items.length) return null;
                return (
                  <div key={t}>
                    <h3 className="flex justify-between text-sm font-semibold">{name}<span className="text-xs font-normal text-muted">{items.length}</span></h3>
                    <ul className="mt-2 space-y-2">
                      {items.map((h) => (
                        <li key={h.id} className="text-sm">
                          <Link href={`/entity/${enc(h.id)}`} className="text-ink/80 hover:text-link hover:underline hover:underline-offset-2">{h.label}</Link>
                          <span className="block text-xs text-muted">
                            {h.matched && h.matched !== h.label ? `“${h.matched}” · ` : ""}{h.match ? MATCH_TEXT[h.match] : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
              {rest.some((h) => !TYPE_GROUP.some(([t]) => t === h.type)) && (
                <div>
                  <h3 className="text-sm font-semibold">Demo entries</h3>
                  <ul className="mt-2 space-y-2 text-sm">
                    {rest.filter((h) => !TYPE_GROUP.some(([t]) => t === h.type)).map((h) => (
                      <li key={h.id}><Link href={`/entity/${enc(h.id)}`} className="text-ink/80 hover:text-link hover:underline">{h.label}</Link></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </main>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 text-xs font-medium tracking-wide text-muted uppercase">{children}</h2>;
}

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="mt-5 max-w-[80ch] rounded-md border border-rule bg-subtle px-4 py-3 text-sm">{children}</p>;
}

function MatchCard({ h, prominent = false }: { h: SearchHit; prominent?: boolean }) {
  return (
    <Link href={`/entity/${enc(h.id)}`}
      className={`group block rounded-lg border border-rule transition-colors hover:border-ink ${prominent ? "p-5" : "p-4"}`}>
      <span className="flex items-baseline justify-between gap-3 text-xs text-muted">
        <span className="capitalize">{h.type}</span>
        <span className="font-mono text-[11px]">{h.id}</span>
      </span>
      <span className={`mt-1 block font-semibold ${prominent ? "text-xl" : ""}`}>{h.label}</span>
      <span className="mt-1 block text-sm text-muted">
        {h.matched && h.matched !== h.label && <>Matched “{h.matched}” · </>}
        {h.match ? MATCH_TEXT[h.match] : ""}
        {h.source_type === "synthetic_fixture" && <span className="ml-2 rounded bg-synthetic/30 px-1.5 py-0.5 text-[11px] text-ink">Synthetic</span>}
      </span>
      <span className="mt-3 inline-flex items-center gap-1 text-sm text-link">
        Open <ArrowRight aria-hidden className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
