"use client";

import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, enc } from "@/lib/api";
import { ReviewBadge, SourceBadge, StatusMark } from "./Badges";

type ClaimData = Awaited<ReturnType<typeof api.claim>>;

const Ctx = createContext<(claimId: string) => void>(() => {});

export function useOpenClaim() {
  return useContext(Ctx);
}

/** A citation chip. Every statement in the UI links to its claim through one of these. */
export function ClaimRef({ id, n, className = "" }: { id: string; n?: number; className?: string }) {
  const open = useOpenClaim();
  return (
    <button
      type="button"
      onClick={() => open(id)}
      title={`Open evidence for ${id}`}
      className={`mx-0.5 inline-flex items-center rounded bg-link-soft px-1 align-baseline text-[0.75em] font-semibold text-link hover:bg-link hover:text-white ${className}`}
    >
      {n !== undefined ? n : id.replace("CLAIM:", "")}
    </button>
  );
}

export function EvidenceDrawerProvider({ children }: { children: React.ReactNode }) {
  const [claimId, setClaimId] = useState<string | null>(null);
  const [data, setData] = useState<ClaimData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const open = useCallback((id: string) => { setClaimId(id); setData(null); setError(null); }, []);

  useEffect(() => {
    if (!claimId) return;
    closeRef.current?.focus();
    api.claim(claimId).then(setData).catch(() => setError(`Could not load ${claimId}. Check that the API is running.`));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setClaimId(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [claimId]);

  return (
    <Ctx.Provider value={open}>
      {children}
      {claimId && (
        <aside
          role="dialog"
          aria-modal="false"
          aria-label={`Evidence for ${claimId}`}
          className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[440px] flex-col border-l border-rule bg-white shadow-2xl animate-[slidein_.18s_ease-out]"
        >
          <div className="flex items-center justify-between border-b border-rule px-5 py-3">
            <h2 className="text-lg font-semibold">Evidence</h2>
            <button ref={closeRef} onClick={() => setClaimId(null)} className="rounded px-2 py-1 text-sm text-muted hover:bg-page">
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
  const predicate = c.predicate.toLowerCase().replaceAll("_", " ");
  return (
    <div className="space-y-5 text-[15px]">
      <p className="text-lg leading-snug">
        <EntityLink id={c.subject_id} label={d.subject_label} onClose={onClose} />{" "}
        <span className="text-muted">{predicate}</span>{" "}
        <EntityLink id={c.object_id} label={d.object_label} onClose={onClose} />
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <SourceBadge type={c.source_type} />
        <ReviewBadge state={c.review_state} />
        <StatusMark status={c.status} />
      </div>

      <figure className="border-l-4 border-ink/80 pl-4">
        <blockquote className="text-[17px] leading-relaxed">{c.source_span}</blockquote>
        <figcaption className="mt-2 text-sm text-muted">
          <a className="ref" href={c.source_url} target="_blank" rel="noreferrer">Open source</a>
          {c.published_at && <> · published {c.published_at}</>}
          {c.retrieved_at && <> · retrieved {c.retrieved_at}</>}
        </figcaption>
      </figure>

      {Object.keys(c.context).length > 0 && (
        <Section title="Context">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(c.context).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
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

      <Section title="Lineage">
        <p className="text-sm">
          Experiment group <b>{c.lineage_id.replace("STUDY:", "")}</b>.{" "}
          {d.lineage_siblings.length > 0 ? (
            <>
              Other claims from the same experiment group. They are not independent confirmation:{" "}
              {d.lineage_siblings.map((id) => <ClaimRef key={id} id={id} />)}
            </>
          ) : (
            "No other claim from this experiment group is indexed."
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
