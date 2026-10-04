import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { api, type Claim } from "@/lib/api";
import {
  aiModel,
  claimKind,
  clean,
  doiOf,
  foundByAi,
  isDrugClaim,
  KIND_LABEL,
  meaning,
  originLabel,
  plain,
} from "@/lib/labels";
import { Ctx, useOpenClaim, type Open } from "@/lib/drawerContext";
import { safeHref } from "@/lib/safeHref";

/** A citation chip: opens the evidence drawer for one claim. */
export function ClaimChip({ id, n }: { id: string; n?: number }) {
  const open = useOpenClaim();
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => open(id)}
      aria-label={`Open the evidence for ${id}`}
      className="h-6 px-1.5 font-mono text-[10px]"
    >
      {n !== undefined ? `[${n}]` : id.replace(/^CLAIM:/, "")}
    </Button>
  );
}

export function EvidenceDrawerProvider({ children }: { children: ReactNode }) {
  const [claimId, setClaimId] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const open = useCallback((id: string) => {
    if (!opener.current)
      opener.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setClaimId(id);
  }, []);
  const close = useCallback(() => {
    setClaimId(null);
    opener.current?.focus(); // keyboard users land back on the citation they opened
    opener.current = null;
  }, []);
  return (
    <Ctx.Provider value={open}>
      {children}
      {claimId && <Drawer claimId={claimId} onClose={close} onOpen={open} />}
    </Ctx.Provider>
  );
}

function Drawer({
  claimId,
  onClose,
  onOpen,
}: {
  claimId: string;
  onClose: () => void;
  onOpen: Open;
}) {
  const q = useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => api.claim(claimId),
    staleTime: 300_000,
    retry: 1,
  });
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-foreground/20" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Evidence details"
        className="absolute inset-y-0 right-0 w-full max-w-lg overflow-y-auto border-l border-border bg-card p-6 shadow-lg"
      >
        <div className="flex items-center justify-between">
          <span className="section-kicker break-all">{claimId}</span>
          <Button
            ref={closeRef}
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close evidence"
          >
            <X />
          </Button>
        </div>
        {q.isPending && <p className="mt-6 text-sm text-muted-foreground">Loading {claimId}…</p>}
        {q.isError && (
          <p role="alert" className="mt-6 text-sm text-destructive">
            Could not load {claimId}. Check that the API is running.
          </p>
        )}
        {q.data && <Body d={q.data} onOpen={onOpen} onClose={onClose} />}
      </aside>
    </div>
  );
}

type Data = Awaited<ReturnType<typeof api.claim>>;

function Body({ d, onOpen, onClose }: { d: Data; onOpen: Open; onClose: () => void }) {
  const c = d.claim;
  const kind = claimKind(c);
  const hypothesis = c.source_type === "ai_generated";
  const href = safeHref(c.source_url);
  const doi = doiOf(c.source_url);
  const tabular = c.source_span.includes("\t");
  return (
    <div className="mt-6 space-y-6">
      <h2 className="text-xl font-semibold leading-snug">
        <EntityLink id={c.subject_id} label={d.subject_label} onClose={onClose} />{" "}
        <span className="font-normal text-muted-foreground">{plain(c.predicate)}</span>{" "}
        <EntityLink id={c.object_id} label={d.object_label} onClose={onClose} />
      </h2>
      <div className="flex flex-wrap gap-2">
        <span className={`evidence-badge evidence-${kind}`}>{KIND_LABEL[kind]}</span>
        <span className="evidence-badge">{c.status.replaceAll("_", " ")}</span>
        <span className="evidence-badge">
          {c.review_state === "reviewed" ? "reviewed" : "unreviewed"}
        </span>
      </div>

      <OriginNote c={c} onOpen={onOpen} />

      <section className="rounded-md bg-muted px-4 py-3 text-sm">
        <h3 className="mb-1 font-semibold">What this means</h3>
        <ul className="list-disc space-y-0.5 pl-4">
          {meaning(c).map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </section>

      <figure className="border-l-2 border-primary pl-5">
        <figcaption className="section-kicker">
          {hypothesis
            ? "The AI's reasoning (not a quotation from any paper)"
            : tabular
              ? "The source record, verbatim"
              : "Exact source excerpt"}
        </figcaption>
        <blockquote className={`mt-3 text-sm leading-6 ${tabular ? "font-mono text-xs" : ""}`}>
          {hypothesis
            ? c.source_span.replace(/^AI hypothesis:\s*/, "")
            : tabular
              ? c.source_span.split("\t").join("  ·  ")
              : c.source_span}
        </blockquote>
      </figure>

      {href ? (
        <Button asChild variant="outline" className="w-full">
          <a href={href} target="_blank" rel="noopener noreferrer">
            {doi
              ? `Open the article (DOI ${doi})`
              : foundByAi(c)
                ? "Open the article"
                : "Open the source"}{" "}
            <ExternalLink />
          </a>
        </Button>
      ) : (
        <p className="border border-border p-3 text-xs text-muted-foreground">
          {c.source_type === "synthetic_fixture"
            ? "Synthetic demo source: no external paper or DOI exists for this claim."
            : "No web link is recorded for this source."}
        </p>
      )}

      <dl className="grid grid-cols-2 gap-4 text-xs">
        <Field k="Predicate" v={c.predicate} mono />
        <Field k="Source type" v={c.source_type} mono />
        <Field k="Published" v={c.published_at ?? "—"} mono />
        <Field k="Retrieved" v={c.retrieved_at ?? "—"} mono />
        <div className="col-span-2">
          <dt className="text-muted-foreground">Extracted by</dt>
          <dd className="mt-1">{c.extraction_method ?? "unknown method"}</dd>
        </div>
        {Object.entries(c.context).map(([k, v]) => (
          <Field key={k} k={k.replaceAll("_", " ")} v={String(v).replaceAll("_", " ")} />
        ))}
        {c.score !== null && (
          <div className="col-span-2">
            <dt className="text-muted-foreground">Score</dt>
            <dd className="mt-1">
              <b>{c.score}</b>: {c.score_definition}
            </dd>
          </div>
        )}
      </dl>

      {d.contradicting_claims.length > 0 && (
        <section className="border-l-2 border-conflict pl-4">
          <h3 className="text-xs font-semibold text-conflict">
            Disagrees with {d.contradicting_claims.length} other claim(s)
          </h3>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Both stay visible. A reviewer decides.
          </p>
          <Chips ids={d.contradicting_claims} onOpen={onOpen} />
        </section>
      )}

      <section>
        <h3 className="text-xs font-semibold">Lineage</h3>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {d.lineage_siblings.length > 0
            ? "Other claims from the same paper or record. They are not independent confirmation."
            : "No other claim from this paper or record is stored. Claims from one record count as one source."}
        </p>
        <p className="mt-1 font-mono text-[11px]">{c.lineage_id}</p>
        <Chips ids={d.lineage_siblings} onOpen={onOpen} />
      </section>

      {c.contributor && (
        <p className="text-xs text-muted-foreground">
          Contributed by {c.contributor}. Lab-reported findings stay unreviewed until a reviewer
          checks them.
        </p>
      )}
      <p className="border-t border-border pt-4 text-xs leading-5 text-muted-foreground">
        Research-support content only. Not clinical guidance.
      </p>
    </div>
  );
}

function Field({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-muted-foreground capitalize">{k}</dt>
      <dd className={`mt-1 break-words ${mono ? "font-mono" : ""}`}>{v}</dd>
    </div>
  );
}

function Chips({ ids, onOpen }: { ids: string[]; onOpen: Open }) {
  if (!ids.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {ids.map((id) => (
        <Button
          key={id}
          variant="outline"
          size="sm"
          onClick={() => onOpen(id)}
          className="h-auto whitespace-normal break-all py-1 text-left font-mono text-[10px]"
        >
          {id.replace(/^CLAIM:/, "")}
        </Button>
      ))}
    </div>
  );
}

function EntityLink({
  id,
  label,
  onClose,
}: {
  id: string;
  label: string | null;
  onClose: () => void;
}) {
  return (
    <Link
      to="/entity/$id"
      params={{ id }}
      onClick={onClose}
      className="font-semibold underline-offset-2 hover:underline"
    >
      {clean(label ?? id)}
    </Link>
  );
}

/** Says plainly who produced a claim when an AI was involved, what was and was not checked, and why. */
function OriginNote({ c, onOpen }: { c: Claim; onOpen: Open }) {
  const model = aiModel(c);
  const checked =
    c.review_state === "reviewed" ? "A reviewer has checked it." : "No human has reviewed it.";
  if (c.source_type === "ai_generated") {
    return (
      <section
        className="rounded-md border border-hypothesis px-4 py-3 text-sm"
        aria-label="Origin: AI hypothesis"
      >
        <h3 className="mb-1 font-semibold text-hypothesis">
          {isDrugClaim(c)
            ? "Treatment idea: AI hypothesis, not a recommendation"
            : "AI hypothesis, not a finding"}
        </h3>
        <p>
          An AI model{model ? ` (${model})` : ""} proposed this link. No paper states it. {checked}
        </p>
        {c.derived_from.length > 0 && (
          <>
            <p className="mt-2">Built from these stored claims (open them to see the sources):</p>
            <Chips ids={c.derived_from} onOpen={onOpen} />
          </>
        )}
      </section>
    );
  }
  if (isDrugClaim(c)) {
    return (
      <section
        className="rounded-md border border-hypothesis px-4 py-3 text-sm"
        aria-label="Origin: treatment idea"
      >
        <h3 className="mb-1 font-semibold text-hypothesis">
          Treatment idea: hypothesis only, not a recommendation
        </h3>
        <p>
          {foundByAi(c)
            ? `An AI model (${model}) read this in the article below.`
            : "Recorded from the source below."}{" "}
          It is stored as a hypothesis. {checked}
        </p>
      </section>
    );
  }
  if (foundByAi(c)) {
    return (
      <section
        className="rounded-md border border-border px-4 py-3 text-sm"
        aria-label="Origin: found by AI"
      >
        <h3 className="mb-1 font-semibold">{originLabel(c)}</h3>
        <p>
          An AI model ({model}) read the paper and proposed this claim; the sentence below was
          checked to appear word for word in it. {checked}
        </p>
      </section>
    );
  }
  return null;
}
