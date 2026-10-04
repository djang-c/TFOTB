import Link from "next/link";
import { api, enc, type SymptomSearch } from "@/lib/api";
import { ApiDown } from "@/components/ApiDown";
import { ClaimRef } from "@/components/EvidenceDrawer";

export const metadata = { title: "Describe symptoms" };

export default async function SymptomsPage(props: PageProps<"/symptoms">) {
  const raw = (await props.searchParams).q;
  const q = (Array.isArray(raw) ? raw[0] : raw ?? "").trim();
  let res: SymptomSearch | null = null;
  if (q) {
    try {
      res = await api.symptoms(q);
    } catch {
      return <ApiDown what="the symptom search" />;
    }
  }
  return (
    <main className="mx-auto max-w-[760px] px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">No diagnosis yet? Describe the symptoms.</h1>
      <p className="mt-2 text-sm text-muted">
        This lists diseases whose recorded symptoms overlap with what you describe, and the genes linked to them. They are
        research hypotheses to take to a clinician or geneticist. They are not diagnoses.
      </p>
      <form action="/symptoms" method="get" className="mt-5 flex gap-2">
        <input
          name="q" defaultValue={q} aria-label="Describe symptoms" placeholder="for example: seizures, vision loss, ataxia"
          className="h-11 flex-1 rounded-md border border-rule bg-sheet px-3 text-sm focus:border-link focus:outline-none focus:ring-4 focus:ring-link/10"
        />
        <button type="submit" className="rounded-md border border-rule px-4 text-sm hover:border-ink">Find candidates</button>
      </form>

      {res && (
        <section className="mt-8 space-y-6">
          <div>
            <h2 className="text-base font-semibold">What we understood</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {res.terms.map((t) => (
                <li key={`${t.text}-${t.id ?? ""}`}>
                  {t.status === "resolved"
                    ? <><span className="font-medium">{t.label}</span> <span className="text-muted">(from &ldquo;{t.text}&rdquo;)</span></>
                    : <span className="text-muted">&ldquo;{t.text}&rdquo; could not be matched to one symptom term{(t.candidates ?? []).length > 0 ? `; did you mean ${(t.candidates ?? []).map((c) => c.label).join(", ")}?` : "."}</span>}
                </li>
              ))}
            </ul>
          </div>

          {res.candidates.length === 0 ? (
            <p className="text-sm text-muted">No candidate diseases to show. Try other words, or HPO symptom IDs such as HP:0001250.</p>
          ) : (
            <div>
              <h2 className="text-base font-semibold">Candidate diseases (research hypotheses)</h2>
              <ol className="mt-2 divide-y divide-rule rounded-lg border border-rule">
                {res.candidates.map((c) => (
                  <li key={c.disease_id} className="px-4 py-3 text-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                      <Link className="ref font-medium" href={`/entity/${enc(c.disease_id)}`}>{c.label}</Link>
                      <span className="text-xs text-muted tabular-nums">
                        covers {c.coverage.toFixed(2)} of what you described &middot; {c.recorded_symptoms} symptoms recorded for it
                      </span>
                    </div>
                    <p className="mt-1 text-muted">
                      Records: {c.matched_labels.join(", ") || "none of them"}
                      {c.unmatched_labels.length > 0 && <>. Does not record: {c.unmatched_labels.join(", ")}</>}
                      {c.recorded_absent.length > 0 && <>. Explicitly records as absent: {c.recorded_absent.length}</>}
                    </p>
                    {c.genes.length > 0 && (
                      <p className="mt-1">
                        Linked genes: {c.genes.map((g, k) => <span key={g.id}>{k > 0 && ", "}{g.label}<ClaimRef id={g.claim_id} /></span>)}
                        <span className="text-muted"> (a link is an association, not proof of cause)</span>
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="space-y-1 text-xs text-muted">
            <p>{res.note}</p>
            <p>{res.definition}</p>
            <p>Source: {res.source}.</p>
          </div>
        </section>
      )}
    </main>
  );
}
