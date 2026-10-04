import { useMutation } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, Laptop, Loader2, ShieldAlert } from "lucide-react";
import { useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { api, type LookupResult, type SearchHit } from "@/lib/api";
import { saveLocal, type LocalTerm } from "@/lib/localTerms";
import { safeHref } from "@/lib/safeHref";

/**
 * What happens when a visitor searches for something the catalogue has never seen.
 * 1. The server checks the text is a term (not a personal identifier) and that it is really unknown.
 * 2. It asks NLM MeSH and Europe PMC. A verified term is added to the shared catalogue with its papers.
 * 3. Anything else stays on THIS device only, and the panel says so.
 * Runs once per term, on an explicit search (Enter), never while typing.
 */
export function LookupPanel({
  term,
  onOpen,
  onOpenLocal,
}: {
  term: string;
  onOpen: (id: string) => void;
  onOpenLocal: (t: LocalTerm) => void;
}) {
  const m = useMutation({ mutationFn: (t: string) => api.lookup(t) });
  useEffect(() => {
    m.mutate(term);
  }, [term]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      className="p-4 text-left text-sm"
      role="status"
      aria-live="polite"
      data-testid="lookup-panel"
    >
      <p className="font-medium">“{term}” is not in the catalogue yet.</p>
      {m.isPending && (
        <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" /> Checking public medical sources (NLM MeSH and
          Europe PMC)…
        </p>
      )}
      {m.isError && (
        <Failed term={term} reason="The server could not be reached." onOpenLocal={onOpenLocal} />
      )}
      {m.data && <Outcome term={term} r={m.data} onOpen={onOpen} onOpenLocal={onOpenLocal} />}
      <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-4 text-muted-foreground">
        <ShieldAlert className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
        Only the term you typed is sent, to those two public services. Do not type patient names or
        identifiers.
      </p>
    </div>
  );
}

function Failed({
  term,
  reason,
  onOpenLocal,
}: {
  term: string;
  reason: string;
  onOpenLocal: (t: LocalTerm) => void;
}) {
  return (
    <div className="mt-2">
      <p className="text-xs text-muted-foreground">{reason}</p>
      <Button
        size="sm"
        variant="outline"
        className="mt-2"
        onClick={() => onOpenLocal(saveLocal(term, "not checked"))}
      >
        <Laptop /> Keep it on this device only
      </Button>
    </div>
  );
}

function Outcome({
  term,
  r,
  onOpen,
  onOpenLocal,
}: {
  term: string;
  r: LookupResult;
  onOpen: (id: string) => void;
  onOpenLocal: (t: LocalTerm) => void;
}) {
  if (r.status === "rejected") return <p className="mt-2 text-xs text-destructive">{r.reason}</p>;
  if (r.status === "known") {
    return (
      <div className="mt-2">
        <p className="text-xs text-muted-foreground">{r.reason}</p>
        <ul className="mt-2 space-y-1">
          {r.results.slice(0, 5).map((h: SearchHit) => (
            <li key={h.id}>
              <Button
                variant="ghost"
                className="h-auto w-full justify-start px-2 py-1.5 text-left font-normal"
                onClick={() => onOpen(h.id)}
              >
                {h.label}{" "}
                <span className="font-mono text-[10px] text-muted-foreground">{h.id}</span>
              </Button>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (r.status === "added") {
    return (
      <div className="mt-2">
        <p className="flex items-start gap-2 text-xs">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-reviewed" />
          <span>
            <b>Verified and added to the shared catalogue:</b> {r.label} ({r.kind}). {r.reason}
          </span>
        </p>
        {r.papers.length > 0 && (
          <div className="mt-3">
            <p className="section-kicker flex items-center gap-1">
              <BookOpen className="size-3" /> PubMed-indexed papers that name it
            </p>
            <ul className="mt-1 space-y-1 text-xs">
              {r.papers.slice(0, 3).map((p) => (
                <li key={p.pmid}>
                  {safeHref(p.url) ? (
                    <a
                      className="underline-offset-2 hover:underline"
                      href={safeHref(p.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {p.title}
                    </a>
                  ) : (
                    p.title
                  )}{" "}
                  <span className="text-muted-foreground">
                    {p.journal} {p.year}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-2 text-[11px] leading-4 text-muted-foreground">{r.note}</p>
        <Button size="sm" className="mt-3" onClick={() => onOpen(r.entity_id)}>
          Open {r.label}
        </Button>
      </div>
    );
  }
  const unavailable = r.status === "unavailable";
  return (
    <div className="mt-2">
      <p className="text-xs">
        <b>{unavailable ? "Could not decide." : "Not verified as a medical term."}</b> {r.reason}
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        {unavailable
          ? "Nothing was added to the shared catalogue. You can keep it on this device and check again later."
          : "It was not added to the shared catalogue. You can keep it on this device only, where it is labelled as unverified."}
      </p>
      <Button
        size="sm"
        variant="outline"
        className="mt-3"
        onClick={() => onOpenLocal(saveLocal(term, unavailable ? "not checked" : r.reason))}
      >
        <Laptop /> Keep it on this device only
      </Button>
      {term.split(/[\s,;]+/).length >= 2 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Describing symptoms?{" "}
          <Link to="/symptoms" search={{ q: term }} className="underline underline-offset-2">
            Search by symptoms instead
          </Link>
          .
        </p>
      )}
    </div>
  );
}
