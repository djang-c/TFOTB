import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { clean } from "@/lib/labels";

export const Route = createFileRoute("/clusters")({ ssr: false, component: ClustersPage });

function ClustersPage() {
  const q = useQuery({ queryKey: ["clusters"], queryFn: api.clusters, retry: 1 });
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-[900px] px-5 py-12">
      <h1 className="text-2xl font-semibold">Diseases grouped by a shared observed mechanism</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {q.data?.note ??
          "An organisation of the evidence under a stated rule: diseases that share an observed mechanism feature (the same compartment and substance), read from papers. It is not a validated clustering and not a claim of shared treatment."}
      </p>
      {q.isPending && <p className="mt-8 text-sm text-muted-foreground">Loading…</p>}
      {q.isError && (
        <p role="alert" className="mt-8 text-sm text-destructive">
          Clusters could not be loaded. Check that the API is running.
        </p>
      )}
      {q.data && q.data.clusters.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">
          No two diseases share an observed mechanism feature in the claims stored so far. Missing
          is not the same as none: more papers may change this.
        </p>
      )}
      <div className="mt-8 space-y-4">
        {q.data?.clusters.map((c) => (
          <article
            key={c.diseases.map((d) => d.id).join("|")}
            className="rounded-lg border border-border p-5"
          >
            <p className="flex flex-wrap gap-2">
              {c.diseases.map((d) => (
                <Button
                  key={d.id}
                  variant="outline"
                  size="sm"
                  onClick={() => void navigate({ to: "/entity/$id", params: { id: d.id } })}
                >
                  {clean(d.label)}
                </Button>
              ))}
            </p>
            <h2 className="mt-4 text-sm font-semibold">Shared features</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {c.shared_features.map((f) => (
                <li key={f.feature}>
                  <b>{f.label}</b>{" "}
                  <span className="text-xs text-muted-foreground">
                    in {f.studies} {f.studies === 1 ? "study" : "studies"}
                  </span>{" "}
                  <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
                    {f.claim_ids.map((id) => (
                      <ClaimChip key={id} id={id} />
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
