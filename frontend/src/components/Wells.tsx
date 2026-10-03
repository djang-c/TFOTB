import type { ChannelComparison } from "@/lib/api";
import { AVAILABILITY_TEXT } from "./Badges";
import { ClaimRef } from "./EvidenceDrawer";

const CHANNEL_NAME: Record<string, string> = {
  phenotype: "Symptoms",
  dna: "DNA",
  rna: "RNA",
  mechanism: "Mechanism",
  dna_variants: "Shared gene",
  rna_effects: "RNA",
  molecular_mechanisms: "Mechanism",
  experimental_findings: "Experiments",
};

/** One assay-plate well per evidence channel. Missing is hatched and says "no data", never 0. */
export function Wells({ comparisons, labels = {} }: { comparisons: ChannelComparison[]; labels?: Record<string, string> }) {
  return (
    <div className={`grid gap-1.5 ${comparisons.length <= 2 ? "grid-cols-2" : comparisons.length === 3 ? "grid-cols-3" : "grid-cols-4"}`} role="list" aria-label="Evidence by channel">
      {comparisons.map((c) => (
        <Well key={c.channel_id} c={c} labels={labels} />
      ))}
    </div>
  );
}

function Well({ c, labels }: { c: ChannelComparison; labels: Record<string, string> }) {
  const name = CHANNEL_NAME[c.channel_id] ?? c.channel_id;
  const refs = [...c.supporting_claim_ids, ...c.contradicting_claim_ids];
  // Both sides have data here but nothing in common: available, yet not a match. Shown neutral.
  const nothingShared = c.availability === "available" && c.score === null && refs.length === 0 && c.context_matches.length === 0;
  const shared = c.score === null
    ? c.context_matches.map((m) => m.replace(/\b(?:HGNC|MONDO|HP|GO):\d+/g, (id) => labels[id] ?? id).replace(/^shared /, ""))
    : [];
  const tone = nothingShared ? "border-rule bg-sheet" : {
    available: "border-ev-reviewed bg-ev-reviewed/8",
    missing: "border-dashed border-ev-gap well-missing",
    incompatible: "border-ev-hypo bg-ev-hypo/5",
    failed: "border-fail bg-fail/5",
  }[c.availability];
  const mark = nothingShared ? "○" : { available: "✓", missing: "—", incompatible: "✕", failed: "!" }[c.availability];
  const note = [...c.context_mismatches, ...c.limitations, ...c.missing_fields.map((f) => `missing: ${f}`)];
  return (
    <div role="listitem" className={`rounded-md border-2 px-2 py-1.5 ${tone}`} title={note.join("; ") || undefined}>
      <div className="flex items-baseline justify-between gap-1">
        <span className="text-xs font-semibold">{name}</span>
        <span aria-hidden className="text-sm font-bold">{mark}</span>
      </div>
      <div className="text-xs text-muted">
        {c.availability === "available" && c.score !== null ? (
          <span title={c.score_definition ?? ""}>overlap {c.score.toFixed(2)}</span>
        ) : nothingShared ? (
          "none in common"
        ) : shared.length > 0 ? (
          <span className="text-ink">shares {shared.slice(0, 2).join(", ")}{shared.length > 2 ? ` +${shared.length - 2}` : ""}</span>
        ) : (
          AVAILABILITY_TEXT[c.availability]
        )}
      </div>
      {refs.length > 0 && (
        <div className="mt-0.5 flex flex-wrap">
          {refs.slice(0, 4).map((id) => (
            <ClaimRef key={id} id={id} className={c.contradicting_claim_ids.includes(id) ? "!bg-ev-conflict/15 !text-ev-conflict" : ""} />
          ))}
          {refs.length > 4 && <span className="text-xs text-muted">+{refs.length - 4}</span>}
        </div>
      )}
    </div>
  );
}
