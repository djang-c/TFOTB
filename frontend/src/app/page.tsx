import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { api, enc, type Entity, type EntityType, type Featured } from "@/lib/api";
import { ApiDown } from "@/components/ApiDown";
import { GAP_KIND } from "@/components/Badges";

const GROUPS: [EntityType, string][] = [
  ["disease", "Diseases"],
  ["gene", "Genes"],
  ["variant", "Variants"],
  ["mechanism", "Mechanisms"],
  ["phenotype", "Phenotypes"],
  ["asset", "Registries and models"],
  ["organization", "Organizations"],
  ["study", "Studies"],
];

export default async function Home() {
  let meta, entities;
  try {
    [meta, entities] = await Promise.all([api.meta(), api.entities()]);
  } catch {
    return <ApiDown what="the atlas" />;
  }
  const byType = (t: EntityType) => entities.items.filter((e: Entity) => e.type === t);
  const synthetic = (meta.counts_by_source_type.synthetic_fixture ?? 0) > 0;
  const featured = meta.featured ?? [];
  const reviewed = meta.counts_by_review_state.reviewed ?? 0;

  return (
    <main className="mx-auto max-w-[1240px] px-4 pt-14 pb-10">
      <h1 className="max-w-[26ch] text-[32px] leading-[1.15] font-semibold tracking-tight text-balance">
        Follow a rare disease to the research that already connects to it.
      </h1>
      <p className="mt-3 max-w-[60ch] text-[15px] leading-relaxed text-muted">
        Each connection shows which evidence supports it, which is missing, and the quoted source
        behind every statement. When nothing is supported, the atlas says what is unknown.
      </p>

      <dl className="mt-6 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <Stat label="Entries" value={entities.items.length} />
        <Stat label="Claims" value={meta.claims} />
        <Stat label="Reviewed" value={`${reviewed} of ${meta.claims}`} />
        <Stat label="Dataset" value={meta.dataset_version} mono />
        <Stat label="As of" value={meta.as_of} mono />
      </dl>

      {synthetic && (
        <p className="mt-6 flex items-start gap-3 rounded-md border border-rule bg-subtle px-4 py-3 text-sm">
          <span aria-hidden className="tape mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full" />
          <span>
            <b className="font-semibold">Synthetic demo data.</b>{" "}
            <span className="text-muted">
              Placeholder names, no biological claim. Real, reviewed sources replace it before any use.
            </span>
          </span>
        </p>
      )}

      {featured.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xs font-medium tracking-wide text-muted uppercase">Start here</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((f) => <FeaturedCard key={f.id} f={f} />)}
          </div>
        </section>
      )}

      <section className="mt-12">
        <h2 className="text-xs font-medium tracking-wide text-muted uppercase">Browse</h2>
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-8 border-t border-rule pt-6 lg:grid-cols-4">
          {GROUPS.map(([t, name]) => {
            const items = byType(t);
            if (!items.length) return null;
            return (
              <div key={t}>
                <h3 className="flex items-baseline justify-between text-sm font-semibold">
                  {name} <span className="text-xs font-normal text-muted tabular-nums">{items.length}</span>
                </h3>
                <ul className="mt-2 space-y-1.5 text-sm">
                  {items.map((e) => (
                    <li key={e.id}>
                      <Link className="text-ink/80 hover:text-link hover:underline hover:underline-offset-2" href={`/entity/${enc(e.id)}`}>
                        {e.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value, mono = false }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className={`font-medium ${mono ? "font-mono text-[13px]" : ""}`}>{value}</dd>
    </div>
  );
}

function FeaturedCard({ f }: { f: Featured }) {
  const detail = f.reason === "connections"
    ? `${f.connections} connections · ${f.assets} reusable ${f.assets === 1 ? "resource" : "resources"}`
    : `Open question: ${(GAP_KIND[f.gap_kind] ?? f.gap_kind).toLowerCase()}`;
  return (
    <Link href={`/entity/${enc(f.id)}`}
      className="group flex flex-col rounded-lg border border-rule p-4 transition-colors hover:border-ink">
      <span className="text-xs text-muted capitalize">{f.type}</span>
      <span className="mt-1 font-semibold">{f.label}</span>
      <span className="mt-1 text-sm text-muted">{detail}</span>
      <span className="mt-4 inline-flex items-center gap-1 text-sm text-link">
        Open <ArrowRight aria-hidden className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
