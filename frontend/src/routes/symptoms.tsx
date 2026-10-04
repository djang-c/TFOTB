import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Copy, Download, X } from "lucide-react";
import { ClaimChip } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { api, type SymptomSearch } from "@/lib/api";
import { clean } from "@/lib/labels";

export const Route = createFileRoute("/symptoms")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Describe symptoms — The Flight of the Buffalo" },
      {
        name: "description",
        content:
          "Compose symptoms to find rare diseases whose recorded phenotypes overlap, with linked genes and the source of each link.",
      },
      { property: "og:title", content: "Symptom search — The Flight of the Buffalo" },
      {
        property: "og:description",
        content: "Research hypotheses from symptom overlap, not clinical diagnoses.",
      },
    ],
  }),
  component: SymptomsPage,
});

const SUGGESTIONS = ["seizures", "vision loss", "ataxia", "hearing loss", "developmental delay"];

function summaryText(terms: string[], res: SymptomSearch): string {
  const lines = [
    `# Symptom overlap summary (research hypotheses — not a diagnosis)`,
    ``,
    `Described: ${terms.join(", ")}`,
    ``,
  ];
  for (const c of res.candidates) {
    lines.push(
      `## ${clean(c.label)} (${c.disease_id})`,
      `- Coverage: ${Math.round(c.coverage * 100)}% of the described symptoms (a share of recorded annotations, not a probability) · ${c.recorded_symptoms} symptoms recorded for it`,
      `- Matched: ${c.matched_labels.join("; ") || "none"}`,
      `- Not recorded: ${c.unmatched_labels.join(", ") || "none"}`,
      `- Recorded although you said absent: ${c.recorded_despite_absent.join(", ") || "none"}`,
      `- Linked genes: ${c.genes.map((g) => `${g.label} (${g.claim_id}, ${g.source})`).join("; ") || "none recorded"}`,
      ``,
    );
  }
  lines.push(
    `Source: HPO phenotype.hpoa and genes_to_disease. Discuss with a clinician or geneticist.`,
  );
  return lines.join("\n");
}

function SymptomsPage() {
  const [terms, setTerms] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [note, setNote] = useState("");
  const query = terms.join(", ");
  const res = useQuery({
    queryKey: ["symptoms", query],
    queryFn: () => api.symptoms(query),
    enabled: terms.length > 0,
    retry: 1,
    staleTime: 60_000,
  });
  const add = (text: string) => {
    const parts = text
      .split(/[,;]/)
      .map((s) => s.trim())
      .filter(Boolean);
    setTerms((t) =>
      [...t, ...parts.filter((p) => !t.some((x) => x.toLowerCase() === p.toLowerCase()))].slice(
        0,
        20,
      ),
    );
    setInput("");
  };
  const data = res.data;
  const present = useMemo(() => (data?.terms ?? []).filter((t) => t.id && !t.absent), [data]);
  const copy = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(summaryText(terms, data));
      setNote("Summary copied.");
    } catch {
      setNote("Could not copy. Use Export summary instead.");
    }
    window.setTimeout(() => setNote(""), 2500);
  };
  const download = () => {
    if (!data) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([summaryText(terms, data)], { type: "text/markdown" }));
    a.download = "symptom-overlap-summary.md";
    a.click();
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <p className="section-kicker">Symptom search</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        No diagnosis yet? Describe symptoms
      </h1>
      <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
        This lists diseases whose recorded symptoms overlap with what you describe, and the genes
        linked to them. They are research hypotheses to take to a clinician or geneticist — not
        clinical diagnoses.
      </p>

      <section className="mt-8 rounded-xl border border-border/70 bg-background p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          {terms.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs"
            >
              {t}
              <button
                aria-label={`Remove ${t}`}
                onClick={() => setTerms(terms.filter((x) => x !== t))}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && input.trim()) {
                e.preventDefault();
                add(input);
              }
              if (e.key === "Backspace" && !input && terms.length) setTerms(terms.slice(0, -1));
            }}
            placeholder={
              terms.length ? "Add another symptom…" : "e.g. seizures, vision loss, no hearing loss"
            }
            aria-label="Describe symptoms"
            className="min-w-[200px] flex-1 bg-transparent py-1.5 text-sm outline-none"
          />
          {terms.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setTerms([])}>
              Clear all
            </Button>
          )}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Separate with commas, press Enter to add. Prefix with “no” to mark a symptom as absent.
          Describe symptoms only: do not type names or other identifying details.
        </p>
      </section>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Quick add</span>
        {SUGGESTIONS.map((s) => (
          <Button
            key={s}
            variant="outline"
            size="sm"
            className="rounded-full text-xs font-normal"
            disabled={terms.includes(s)}
            onClick={() => add(s)}
          >
            {s}
          </Button>
        ))}
      </div>

      {res.isPending && terms.length > 0 && (
        <p className="mt-10 text-sm text-muted-foreground">Searching…</p>
      )}
      {res.isError && (
        <p role="alert" className="mt-10 text-sm text-destructive">
          The symptom search could not be reached. Check that the API is running.
        </p>
      )}

      {data && terms.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold">What we understood</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {data.terms.map((t) => (
              <li
                key={`${t.text}-${t.id ?? ""}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 text-sm"
              >
                <span className="text-muted-foreground">
                  “{t.absent ? "no " : ""}
                  {t.text}”
                </span>
                {t.id ? (
                  <span className="text-right">
                    {t.absent && <span className="mr-1 text-conflict">absent:</span>}
                    <span className="font-medium">{t.label}</span>{" "}
                    <span className="font-mono text-[11px] text-muted-foreground">{t.id}</span>
                  </span>
                ) : (
                  <span className="text-right text-xs text-conflict">
                    Not recognised
                    {(t.candidates ?? []).length > 0 && (
                      <>
                        {" "}
                        — did you mean{" "}
                        {(t.candidates ?? []).slice(0, 3).map((c, i) => (
                          <span key={c.id}>
                            {i > 0 && ", "}
                            <button
                              className="text-primary underline"
                              onClick={() =>
                                setTerms(
                                  terms.map((x) =>
                                    x.toLowerCase().includes(t.text.toLowerCase())
                                      ? `${t.absent ? "no " : ""}${c.label.toLowerCase()}`
                                      : x,
                                  ),
                                )
                              }
                            >
                              {c.label}
                            </button>
                          </span>
                        ))}
                        ?
                      </>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data && terms.length > 0 && (
        <section className="mt-10">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">
              Candidate diseases{" "}
              <span className="font-normal text-muted-foreground">· {data.candidates.length}</span>
            </h2>
            {data.candidates.length > 0 && (
              <div className="flex items-center gap-2">
                {note && (
                  <span role="status" className="text-xs text-muted-foreground">
                    {note}
                  </span>
                )}
                <Button variant="outline" size="sm" onClick={() => void copy()}>
                  <Copy /> Take to clinic
                </Button>
                <Button variant="outline" size="sm" onClick={download}>
                  <Download /> Export summary
                </Button>
              </div>
            )}
          </div>
          {data.candidates.length === 0 && (
            <p className="mt-4 rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No recorded disease overlaps these symptoms yet. Try a quick-add suggestion, or other
              words.{" "}
              {present.length === 0 && "A symptom marked absent is not used to find diseases."}
            </p>
          )}
          <ol className="mt-4 space-y-4">
            {data.candidates.map((c, i) => (
              <li key={c.disease_id} className="rounded-xl border border-border/70 p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <span className="mr-2 font-mono text-xs text-muted-foreground">#{i + 1}</span>
                    <Link
                      to="/entity/$id"
                      params={{ id: c.disease_id }}
                      className="text-base font-semibold text-primary hover:underline"
                    >
                      {clean(c.label)}
                    </Link>{" "}
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {c.disease_id}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    covers {Math.round(c.coverage * 100)}% of described symptoms ·{" "}
                    {c.recorded_symptoms} recorded symptoms total
                  </span>
                </div>
                <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${c.coverage * 100}%` }} />
                </div>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-muted-foreground">
                      <tr>
                        <th className="py-1.5 font-normal">Described symptom</th>
                        <th className="py-1.5 font-normal">Record</th>
                        <th className="py-1.5 font-normal">Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {present.map((p) => {
                        const hit = c.matched_labels.includes(p.label);
                        return (
                          <tr key={p.id} className="border-t border-border/60">
                            <td className="py-2">{p.label}</td>
                            <td>
                              {hit ? (
                                <span className="text-reviewed">matched</span>
                              ) : (
                                <span className="text-muted-foreground">not recorded</span>
                              )}
                            </td>
                            <td>
                              {hit ? (
                                <span className="evidence-badge evidence-database">
                                  HPO record, unreviewed
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                          </tr>
                        );
                      })}
                      {c.recorded_despite_absent.map((l) => (
                        <tr key={l} className="border-t border-border/60">
                          <td className="py-2">
                            {l} <span className="text-muted-foreground">(you said absent)</span>
                          </td>
                          <td className="text-conflict">recorded for disease</td>
                          <td>
                            <span className="evidence-badge evidence-conflict">conflict</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Linked genes:</span>
                  {c.genes.length ? (
                    c.genes.map((g) => (
                      <span key={g.claim_id} className="inline-flex items-center gap-1.5">
                        <span className="text-primary">{g.label}</span>
                        <ClaimChip id={g.claim_id} />
                      </span>
                    ))
                  ) : (
                    <span className="text-muted-foreground">none recorded</span>
                  )}
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-6 text-[11px] leading-5 text-muted-foreground">
            {data.note} {data.definition}
          </p>
        </section>
      )}
    </div>
  );
}
