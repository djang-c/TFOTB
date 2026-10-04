"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, enc } from "@/lib/api";
import { ReviewBadge, SourceBadge, StatusMark } from "./Badges";

type ClaimData = Awaited<ReturnType<typeof api.claim>>;

const Ctx = createContext<(claimId: string) => void>(() => {});

export function useOpenClaim() {
  return useContext(Ctx);
}

// One fetch per claim per page, shared by the hover preview and the drawer.
const claimCache = new Map<string, Promise<ClaimData>>();
function loadClaim(id: string): Promise<ClaimData> {
  if (!claimCache.has(id)) claimCache.set(id, api.claim(id));
  return claimCache.get(id)!;
}

/** Plain-language reading of each relationship. Wording never claims more than the predicate does. */
export const PREDICATE_PLAIN: Record<string, string> = {
  AFFECTS_TRANSCRIPT: "affects the RNA transcript",
  ASSOCIATED_WITH_PHENOTYPE: "is reported with the symptom",
  HAS_OBSERVED_RNA_EFFECT: "has an observed RNA effect on",
  HAS_PREDICTED_RNA_EFFECT: "is predicted (not observed) to have an RNA effect on",
  PERTURBS_MECHANISM: "disrupts the biological process",
  SUPPORTED_BY: "is supported by",
  CONTRADICTED_BY: "is contradicted by",
  INVESTIGATED_IN: "was studied in",
  ASSET_RELEVANT_TO: "lists as a condition",
  SIMULATES_WORKFLOW_FOR: "simulates a lab workflow (engineering only) for",
  GENE_ASSOCIATED_WITH_DISEASE: "is linked to",
  ACCUMULATES_IN_COMPARTMENT: "shows build-up in",
  SHARES_PATHOGENIC_PATHWAY_WITH: "may share a disease process with",
  CANDIDATE_THERAPY_FOR: "is a treatment idea (not a recommendation) for",
};

/** What a reader should take from a claim, before any detail. */
function meaning(c: ClaimData["claim"]): string[] {
  const out = [{
    database_record: "Copied from a public reference database; the record is quoted below.",
    published: "Quoted from a published paper.",
    lab_reported: "Reported by a lab; not peer reviewed.",
    synthetic_fixture: "Made-up demo data. Not a real finding.",
    ai_generated: "A hypothesis written by an AI model, not found in any source. It never counts as evidence.",
  }[c.source_type]];
  // Origin labels (PLAN revision 2026-10-04): the label, not a review gate, is the protection.
  if (foundByAi(c)) out.push("Found by AI in this article and checked word for word against it; not reviewed by a human.");
  if (c.predicate === "GENE_ASSOCIATED_WITH_DISEASE") out.push("A link between a gene and a disease is an association; on its own it does not show the gene causes it.");
  if (c.predicate === "ASSET_RELEVANT_TO" && c.subject_id.startsWith("NCT:")) out.push("The study's registry record names this condition. That alone says nothing about what the study found.");
  if (c.status === "computational_prediction") out.push("This is a computer prediction, not an observation.");
  if (c.status === "inference") out.push("This is an inference, not something directly observed.");
  if (["SHARES_PATHOGENIC_PATHWAY_WITH", "CANDIDATE_THERAPY_FOR"].includes(c.predicate)) out.push("Recorded as a hypothesis only, never as a finding.");
  out.push(c.review_state === "reviewed" ? "Reviewed by an expert." : c.review_state === "disputed" ? "Disputed: a reviewer disagrees." : "Not reviewed by an expert.");
  return out;
}

/** The AI model named in the claim's extraction method ("llm:<model>@<prompt>"), if an AI made it. */
function aiModel(c: ClaimData["claim"]): string | null {
  return /^llm:([^@]+)@/.exec(c.extraction_method ?? "")?.[1] ?? null;
}

/** A claim an AI model read out of a published paper (as opposed to a database record or an AI hypothesis). */
function foundByAi(c: ClaimData["claim"]): boolean {
  return c.source_type === "published" && aiModel(c) !== null;
}

const NumCtx = createContext<{ number: (id: string) => number }>({ number: () => 0 });

/** Numbers citations in the order they first appear on the page, like footnotes. */
export function CitationNumbers({ children }: { children: React.ReactNode }) {
  const seen = useRef(new Map<string, number>());
  const number = useCallback((id: string) => {
    if (!seen.current.has(id)) seen.current.set(id, seen.current.size + 1);
    return seen.current.get(id)!;
  }, []);
  return <NumCtx.Provider value={{ number }}>{children}</NumCtx.Provider>;
}

/** A citation: a numbered superscript. Hover (or focus) previews the quote; click opens the evidence. */
export function ClaimRef({ id, n, className = "" }: { id: string; n?: number; className?: string }) {
  const open = useOpenClaim();
  const numbers = useContext(NumCtx);
  const num = n ?? numbers.number(id);
  const [preview, setPreview] = useState<ClaimData | null>(null);
  const [show, setShow] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const enter = () => {
    timer.current = setTimeout(() => {
      setShow(true);
      loadClaim(id).then(setPreview).catch(() => setShow(false));
    }, 250);
  };
  const leave = () => { clearTimeout(timer.current); setShow(false); };
  return (
    <span className="relative inline-block" onMouseEnter={enter} onMouseLeave={leave}>
      <button
        type="button"
        onClick={() => open(id)}
        onFocus={enter}
        onBlur={leave}
        aria-label={`Citation ${num}: open the evidence`}
        className={`mx-px align-super text-[0.7em] leading-none font-semibold text-link tabular-nums hover:underline ${className}`}
      >
        [{num}]
      </button>
      {show && (
        <span role="tooltip" className="absolute bottom-full left-1/2 z-50 mb-1.5 block w-[300px] -translate-x-1/2 rounded-lg border border-rule bg-sheet p-3 text-left text-xs leading-relaxed font-normal text-ink shadow-[0_8px_24px_rgba(17,24,39,0.1)]">
          {preview ? (
            <>
              <span className="block text-muted">
                {preview.subject_label ?? preview.claim.subject_id} {PREDICATE_PLAIN[preview.claim.predicate] ?? preview.claim.predicate.toLowerCase()} {preview.object_label ?? preview.claim.object_id}
              </span>
              <span className="mt-1.5 block border-l-2 border-ink/60 pl-2 font-mono text-[11px] break-words">
                {preview.claim.source_span.length > 180 ? `${preview.claim.source_span.slice(0, 180)}…` : preview.claim.source_span.replaceAll("\t", " · ")}
              </span>
              {preview.claim.source_type === "ai_generated" && <span className="mt-1.5 block font-semibold text-ev-hypo">AI hypothesis, not a finding.</span>}
              {foundByAi(preview.claim) && <span className="mt-1.5 block text-muted">Found by AI in the paper. Not checked by a human unless it says so.</span>}
              <span className="mt-1.5 block text-muted">{meaning(preview.claim).at(-1)} Click for the full evidence.</span>
            </>
          ) : (
            <span className="text-muted">Loading…</span>
          )}
        </span>
      )}
    </span>
  );
}

export function EvidenceDrawerProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [claimId, setClaimId] = useState<string | null>(null);
  const [data, setData] = useState<ClaimData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const open = useCallback((id: string) => { setClaimId(id); setData(null); setError(null); }, []);

  useEffect(() => {
    if (!claimId) return;
    closeRef.current?.focus();
    loadClaim(claimId).then(setData).catch(() => setError(`Could not load ${claimId}. Check that the API is running.`));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setClaimId(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [claimId]);

  return (
    <Ctx.Provider value={open}>
      {/* Keyed by page so footnote numbers restart at [1] on every page. */}
      <CitationNumbers key={pathname}>{children}</CitationNumbers>
      {claimId && (
        <aside
          role="dialog"
          aria-modal="false"
          aria-label={`Evidence for ${claimId}`}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[460px] flex-col border-l border-rule bg-sheet shadow-[-8px_0_24px_rgba(17,24,39,0.06)] animate-[slidein_.18s_ease-out]"
        >
          <div className="flex items-center justify-between border-b border-rule px-5 py-3">
            <h2 className="text-base font-semibold">Evidence</h2>
            <button ref={closeRef} onClick={() => setClaimId(null)} className="rounded px-2 py-1 text-sm text-muted hover:bg-subtle">
              Close
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {error && <p className="text-sm text-fail">{error}</p>}
            {!data && !error && <p className="text-sm text-muted">Loading {claimId}</p>}
            {data && <ClaimBody d={data} onClose={() => setClaimId(null)} />}
          </div>
        </aside>
      )}
    </Ctx.Provider>
  );
}

function ClaimBody({ d, onClose }: { d: ClaimData; onClose: () => void }) {
  const c = d.claim;
  const predicate = PREDICATE_PLAIN[c.predicate] ?? c.predicate.toLowerCase().replaceAll("_", " ");
  const tabular = c.source_span.includes("\t");
  const hypothesis = c.source_type === "ai_generated";
  return (
    <div className="space-y-5 text-[15px]">
      <p className="text-[17px] leading-snug">
        <EntityLink id={c.subject_id} label={d.subject_label} onClose={onClose} />{" "}
        <span className="text-muted">{predicate}</span>{" "}
        <EntityLink id={c.object_id} label={d.object_label} onClose={onClose} />
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <SourceBadge type={c.source_type} />
        <ReviewBadge state={c.review_state} />
        <StatusMark status={c.status} />
      </div>

      <OriginNote c={c} />

      <section className="rounded-md bg-subtle px-4 py-3 text-sm">
        <h3 className="mb-1 font-semibold">What this means</h3>
        <ul className="list-disc space-y-0.5 pl-4">{meaning(c).map((m) => <li key={m}>{m}</li>)}</ul>
      </section>

      <figure className="border-l-2 border-ink/70 pl-4">
        <figcaption className="mb-1 text-xs text-muted">
          {hypothesis ? "The AI's reasoning (not a quotation from any paper)" : tabular ? "The source record, verbatim" : "The source, quoted verbatim"}
        </figcaption>
        <blockquote className={tabular ? "font-mono text-[13px] break-words" : "text-[16px] leading-relaxed"}>
          {hypothesis ? c.source_span.replace(/^AI hypothesis:\s*/, "") : tabular ? c.source_span.split("\t").join("  ·  ") : c.source_span}
        </blockquote>
        <figcaption className="mt-2 text-sm text-muted">
          {c.source_url.startsWith("http") && <a className="ref" href={c.source_url} target="_blank" rel="noreferrer">{foundByAi(c) ? "Open the article" : "Open source"}</a>}
          {c.published_at && <> · published {c.published_at}</>}
          {c.retrieved_at && <> · retrieved {c.retrieved_at}</>}
        </figcaption>
      </figure>

      {Object.keys(c.context).length > 0 && (
        <Section title="Context">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(c.context).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{CONTEXT_LABEL[k] ?? k.replaceAll("_", " ")}</dt>
                <dd>{String(v).replaceAll("_", " ")}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {c.score !== null && (
        <Section title="Score">
          <p className="text-sm"><b>{c.score}</b>: {c.score_definition}</p>
        </Section>
      )}

      {d.contradicting_claims.length > 0 && (
        <Section title="Disagrees with">
          <p className="text-sm">
            {d.contradicting_claims.map((id) => <ClaimRef key={id} id={id} />)} Both stay visible; a reviewer decides.
          </p>
        </Section>
      )}

      <Section title={c.lineage_id.startsWith("STUDY:") ? "Lineage" : "Where it comes from"}>
        <p className="text-sm">
          {c.lineage_id.startsWith("STUDY:")
            ? <>Experiment group <b>{c.lineage_id.replace("STUDY:", "")}</b>.{" "}</>
            : <>Record <b>{c.lineage_id.replace(/^SOURCE:/, "")}</b>.{" "}</>}
          {d.lineage_siblings.length > 0 ? (
            <>
              Other claims from the same experiment group. They are not independent confirmation:{" "}
              {d.lineage_siblings.map((id) => <ClaimRef key={id} id={id} />)}
            </>
          ) : (
            c.lineage_id.startsWith("STUDY:") ? "No other claim from this experiment group is indexed." : "Claims from the same record count as one source, not several."
          )}
        </p>
      </Section>

      {c.contributor && (
        <Section title="Contributed by">
          <p className="text-sm">{c.contributor}. Lab-reported findings stay unreviewed until a reviewer checks them.</p>
        </Section>
      )}

      <p className="border-t border-rule pt-3 text-xs text-muted">
        {c.claim_id} · extracted by {c.extraction_method ?? "unknown method"} · schema {c.schema_version}
      </p>
    </div>
  );
}

const CONTEXT_LABEL: Record<string, string> = {
  association_type: "Association type",
  via: "Through record",
  upstream: "Upstream source",
  listed_conditions: "All listed conditions",
  study_title: "Study",
};

/** Says plainly who produced a claim when an AI was involved, and what was and was not checked. */
function OriginNote({ c }: { c: ClaimData["claim"] }) {
  const model = aiModel(c);
  const checked = c.review_state === "reviewed" ? "A reviewer has checked it." : "No human has reviewed it.";
  if (c.source_type === "ai_generated") {
    return (
      <section className="rounded-md border border-ev-hypo bg-white px-4 py-3 text-sm" aria-label="Origin: AI hypothesis">
        <h3 className="mb-1 font-semibold text-ev-hypo">AI hypothesis, not a finding</h3>
        <p>
          An AI model{model ? ` (${model})` : ""} proposed this link. No paper states it. {checked}
        </p>
        {c.derived_from.length > 0 && (
          <p className="mt-1">
            It was built from these stored claims: {c.derived_from.map((id) => <ClaimRef key={id} id={id} />)}
          </p>
        )}
      </section>
    );
  }
  if (foundByAi(c)) {
    return (
      <section className="rounded-md border border-rule bg-white px-4 py-3 text-sm" aria-label="Origin: found by AI">
        <h3 className="mb-1 font-semibold">Found by AI in this article</h3>
        <p>
          An AI model ({model}) read the paper and proposed this claim; the sentence below was checked to appear word
          for word in it. {checked}{" "}
          <a className="ref" href={c.source_url} target="_blank" rel="noreferrer">Open the article</a>.
        </p>
      </section>
    );
  }
  return null;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function EntityLink({ id, label, onClose }: { id: string; label: string | null; onClose: () => void }) {
  return (
    <Link href={`/entity/${enc(id)}`} onClick={onClose} className="ref font-semibold">
      {label ?? id}
    </Link>
  );
}
