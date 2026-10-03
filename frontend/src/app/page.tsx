import Link from "next/link";
import { api, enc, type Entity, type EntityType } from "@/lib/api";
import { ApiDown } from "@/components/ApiDown";

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

  return (
    <main className="mx-auto grid max-w-[1240px] gap-10 px-4 py-10 lg:grid-cols-[1fr_300px]">
      <div>
        <h1 className="max-w-[30ch] font-serif text-3xl font-semibold leading-tight">
          Follow a rare disease to the research that already connects to it.
        </h1>
        <p className="mt-3 max-w-[62ch] text-muted">
          Each connection shows which evidence supports it, which is missing, and the quoted source
          behind every statement. When nothing is supported, the atlas says what is unknown.
        </p>
        <p className="mt-5 text-sm">
          Start with{" "}
          <Link className="ref font-medium" href={`/entity/${enc("SYN:disease-a")}`}>Disease A</Link>{" "}
          (connections and a reusable registry) or{" "}
          <Link className="ref font-medium" href={`/entity/${enc("SYN:variant-vus-1")}`}>an uncertain variant</Link>{" "}
          (an honest gap).
        </p>

        <div className="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-2 xl:grid-cols-3">
          {GROUPS.map(([t, name]) => {
            const items = byType(t);
            if (!items.length) return null;
            return (
              <section key={t}>
                <h2 className="border-b border-rule pb-1 font-serif text-lg font-semibold">
                  {name} <span className="text-sm font-normal text-muted">{items.length}</span>
                </h2>
                <ul className="mt-2 space-y-1">
                  {items.map((e) => (
                    <li key={e.id}>
                      <Link className="ref" href={`/entity/${enc(e.id)}`}>{e.label}</Link>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      </div>

      <aside className="h-fit rounded-md border border-rule bg-white p-4 text-sm">
        <h2 className="font-serif text-base font-semibold">About this dataset</h2>
        <div className="tape my-3 h-1.5 rounded-sm" aria-hidden />
        <p>
          Everything shown is <b>synthetic demo data</b> with placeholder names. It makes no
          biological claim. Real, reviewed sources replace it before any use.
        </p>
        <dl className="mt-4 grid grid-cols-[1fr_auto] gap-y-1">
          <dt className="text-muted">Version</dt><dd>{meta.dataset_version}</dd>
          <dt className="text-muted">As of</dt><dd>{meta.as_of}</dd>
          <dt className="text-muted">Schema</dt><dd>{meta.schema_version}</dd>
          <dt className="text-muted">Claims</dt><dd>{meta.claims}</dd>
          {Object.entries(meta.counts_by_review_state).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="pl-3 text-muted">{k}</dt><dd>{v}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </main>
  );
}
