import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { PageSkeleton } from "@/components/PageSkeleton";
import { z } from "zod";
import { CatalogSearch } from "@/components/CatalogSearch";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Reveal } from "@/components/explorer/Common";
import { clustersOf, type Cluster } from "@/lib/clusters";
import { clean, EVIDENCE_BADGE, plain } from "@/lib/labels";
import { useEntity, useRelatedDiseases } from "@/lib/queries";

export const Route = createFileRoute("/clusters")({
  ssr: false,
  validateSearch: z.object({ id: z.string().optional().catch(undefined) }),
  head: () => ({ meta: [{ title: "Clusters — The Flight of the Buffalo" }] }),
  component: ClustersPage,
});

function ClustersPage() {
  const { id } = Route.useSearch();
  if (!id) return <NeedSearch />;
  return <Clusters key={id} id={id} />;
}

function NeedSearch() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-xl px-6 py-24 text-center">
      <h1 className="text-2xl font-semibold">Search a disease first</h1>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">
        A cluster only means something next to the disease you are looking into, so this page opens
        after a search.
      </p>
      <CatalogSearch
        className="mt-6 text-left"
        onSelect={(e) => void navigate({ to: "/clusters", search: { id: e.id } })}
        placeholder="Search a disease"
      />
    </div>
  );
}

function Clusters({ id }: { id: string }) {
  const entity = useEntity(id);
  const q = useRelatedDiseases(id);
  const name = entity.data ? clean(entity.data.entity.label) : id;
  const d = q.data;
  const clusters = d?.applies ? clustersOf(d) : [];
  return (
    <div className="px-5 py-8 lg:px-10">
      <header className="border-b border-border pb-6">
        <p className="section-kicker">Clusters</p>
        <h1 className="mt-2 text-3xl font-semibold">Clusters around {name}</h1>
      </header>

      <section
        aria-label="What is a cluster"
        className="mt-6 grid gap-6 rounded-lg border border-border bg-muted/30 p-6 text-sm leading-6 lg:grid-cols-3"
      >
        <div>
          <h2 className="font-semibold">What is a cluster?</h2>
          <p className="mt-1 text-muted-foreground">
            A cluster is a group of diseases that have <strong>one specific thing</strong> in common
            with {name}: the same gene, the same mechanism reported in papers, the same parent
            disease, or a similar set of symptoms. Each cluster below is named after that one shared
            thing. A disease can sit in several clusters at once.
          </p>
        </div>
        <div>
          <h2 className="font-semibold">Why it is useful</h2>
          <p className="mt-1 text-muted-foreground">
            Diseases in the same cluster are candidates for shared research. A lab model, a test or
            a treatment idea studied in one of them may be worth checking in the others. Rare
            diseases have few papers each, so a cluster pools what is known.
          </p>
        </div>
        <div>
          <h2 className="font-semibold">What it is not</h2>
          <p className="mt-1 text-muted-foreground">
            Being in a cluster does not mean the diseases have the same cause, the same treatment or
            the same outcome. Clusters marked as hypotheses come from a suggestion by a paper or an
            AI, not from a finding. Nothing here is a diagnosis.
          </p>
        </div>
      </section>

      {q.isPending && (
        <div className="mt-8">
          <p className="mb-4 text-sm text-muted-foreground">
            Comparing {name} against every disease in the reference files…
          </p>
          <PageSkeleton label="Comparing diseases" />
        </div>
      )}
      {q.isError && (
        <p role="alert" className="mt-8 text-sm text-destructive">
          Clusters could not be loaded.
        </p>
      )}
      {d && !d.applies && (
        <p className="mt-8 text-sm text-muted-foreground">
          Clusters are built for diseases. {name} is not a disease: open its{" "}
          <Link to="/entity/$id" params={{ id }} className="text-primary underline">
            dossier
          </Link>{" "}
          to see the diseases linked to it.
        </p>
      )}
      {d?.applies && d.none && (
        <div className="mt-8 rounded-md border border-dashed border-border p-5">
          <p className="text-sm font-semibold">No clusters: no similarities found.</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{d.note}</p>
        </div>
      )}
      {clusters.length > 0 && (
        <>
          <p className="mt-8 text-xs text-muted-foreground">
            {clusters.length} clusters · {d?.total} diseases in total
          </p>
          <div className="mt-3 gap-4 md:columns-2 2xl:columns-3">
            {clusters.map((c) => (
              <ClusterCard key={c.key} c={c} entryName={name} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ClusterCard({ c, entryName }: { c: Cluster; entryName: string }) {
  const badge = EVIDENCE_BADGE[c.members[0]!.reason.evidence];
  return (
    <article className="mb-4 flex max-h-[28rem] break-inside-avoid flex-col rounded-lg border border-border bg-card">
      <div className="border-b border-border p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-sm font-semibold leading-5">{c.title}</h2>
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
            {c.members.length + 1} diseases
          </span>
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{c.why}</p>
        <span className={`evidence-badge mt-2 inline-block ${badge.cls}`}>{badge.text}</span>
      </div>
      <ul className="flex-1 space-y-2 overflow-y-auto p-5 text-xs leading-5">
        <li className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-primary" />
          <strong>{entryName}</strong>
          <span className="text-muted-foreground">the disease you searched</span>
        </li>
        <Reveal
          items={c.members}
          first={10}
          noun="diseases"
          render={(xs) =>
            xs.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="size-2 rounded-full bg-reviewed" />
                <Link
                  to="/entity/$id"
                  params={{ id: m.id }}
                  className="font-medium hover:text-primary hover:underline"
                >
                  {clean(m.label)}
                </Link>
                {m.reason.kind === "symptoms" && (
                  <span className="font-mono text-muted-foreground">
                    {m.reason.score?.toFixed(2)}
                  </span>
                )}
                {m.reason.claim_ids.slice(0, 2).map((cid) => (
                  <ClaimChip key={cid} id={cid} />
                ))}
                {m.reason.kind === "symptoms" && m.reason.shared?.length ? (
                  <span className="block w-full pl-4 text-[11px] text-muted-foreground">
                    shares {m.reason.shared.join(", ")}
                  </span>
                ) : null}
                {(m.reason.kind === "paper_link" || m.reason.kind === "ai_hypothesis") && (
                  <span className="block w-full pl-4 text-[11px] text-muted-foreground">
                    {plain(m.reason.label)}: “{m.reason.detail}”
                  </span>
                )}
              </li>
            ))
          }
        />
      </ul>
    </article>
  );
}
