import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { clean } from "@/lib/labels";

export const Route = createFileRoute("/symptoms")({
  ssr: false,
  validateSearch: z.object({ q: z.string().optional().catch(undefined) }),
  component: SymptomsPage,
});

function SymptomsPage() {
  const { q = "" } = Route.useSearch();
  const navigate = useNavigate();
  const [text, setText] = useState(q);
  const res = useQuery({
    queryKey: ["symptoms", q],
    queryFn: () => api.symptoms(q),
    enabled: q.trim().length > 0,
    retry: 1,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void navigate({ to: "/symptoms", search: { q: text.trim() || undefined } });
  };
  const open = (id: string) => void navigate({ to: "/explorer", search: { id } });
  return (
    <div className="mx-auto max-w-[760px] px-5 py-12">
      <h1 className="text-2xl font-semibold">No diagnosis yet? Describe the symptoms.</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        This lists diseases whose recorded symptoms overlap with what you describe, and the genes
        linked to them. They are research hypotheses to take to a clinician or geneticist. They are
        not diagnoses.
      </p>
      <form onSubmit={submit} role="search" className="mt-5 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Describe symptoms"
          placeholder="for example: seizures, vision loss, ataxia"
          className="h-11 flex-1 rounded-md border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10"
        />
        <Button type="submit" variant="outline" className="h-11 px-4">
          Find candidates
        </Button>
      </form>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Describe symptoms only. Do not type names or other identifying details.
      </p>
      {res.isPending && q && <p className="mt-8 text-sm text-muted-foreground">Searching…</p>}
      {res.isError && (
        <p role="alert" className="mt-8 text-sm text-destructive">
          The symptom search could not be reached. Check that the API is running.
        </p>
      )}
      {res.data && (
        <section className="mt-8 space-y-6">
          <div>
            <h2 className="text-base font-semibold">What we understood</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {res.data.terms.map((t) => (
                <li key={`${t.text}-${t.id ?? ""}`}>
                  {t.status === "resolved" ? (
                    <>
                      <span className="font-medium">{t.label}</span>{" "}
                      <span className="text-muted-foreground">(from “{t.text}”)</span>
                    </>
                  ) : (
                    <span className="text-muted-foreground">
                      “{t.text}” could not be matched to one symptom term
                      {(t.candidates ?? []).length > 0
                        ? `; did you mean ${(t.candidates ?? []).map((c) => c.label).join(", ")}?`
                        : "."}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
          {res.data.candidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No candidate diseases to show. Try other words, or HPO symptom IDs such as HP:0001250.{" "}
              {res.data.note}
            </p>
          ) : (
            <div>
              <h2 className="text-base font-semibold">Candidate diseases (research hypotheses)</h2>
              <ol className="mt-2 divide-y divide-border rounded-lg border border-border">
                {res.data.candidates.map((c) => (
                  <li key={c.disease_id} className="px-4 py-3 text-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                      <Button
                        variant="link"
                        className="h-auto p-0 font-medium"
                        onClick={() => open(c.disease_id)}
                      >
                        {clean(c.label)}
                      </Button>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        covers {c.coverage.toFixed(2)} of what you described · {c.recorded_symptoms}{" "}
                        symptoms recorded for it
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Matches: {c.matched_labels.join(", ") || "none"}
                      {c.unmatched_labels.length > 0 && (
                        <> · not recorded: {c.unmatched_labels.join(", ")}</>
                      )}
                      {c.recorded_absent.length > 0 && (
                        <> · recorded as absent: {c.recorded_absent.join(", ")}</>
                      )}
                    </p>
                    {c.genes.length > 0 && (
                      <p className="mt-1 text-xs">
                        Linked genes:{" "}
                        {c.genes.map((g) => (
                          <span key={g.id} className="mr-2">
                            {g.label} <ClaimChip id={g.claim_id} />
                          </span>
                        ))}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
              <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
                {res.data.definition} These numbers are shares of recorded annotations. They are not
                probabilities and have not been validated against any ground truth.
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
