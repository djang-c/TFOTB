import { BookOpen, ChevronRight } from "lucide-react";
import { useOpenClaim } from "@/lib/drawerContext";
import { Button } from "@/components/ui/button";
import type { Claim } from "@/lib/api";
import { claimKind, KIND_LABEL, originLabel, plain } from "@/lib/labels";

export function Claims({ claims, labelOf }: { claims: Claim[]; labelOf: (id: string) => string }) {
  const open = useOpenClaim();
  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Claims and evidence</h3>
        <span className="text-xs text-muted-foreground">{claims.length} claims</span>
      </div>
      <p className="mb-4 text-[11px] leading-4 text-muted-foreground">
        Each claim shows where it came from. Open one to read the exact passage and its source link.
      </p>
      <div className="space-y-2">
        {claims.map((c) => {
          const kind = claimKind(c);
          return (
            <Button
              key={c.claim_id}
              variant="outline"
              onClick={() => open(c.claim_id)}
              className="h-auto w-full items-start justify-start gap-3 whitespace-normal p-3 text-left"
            >
              <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <strong className="block text-xs leading-5">
                  {labelOf(c.subject_id)} · {plain(c.predicate)} · {labelOf(c.object_id)}
                </strong>
                <span className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className={`evidence-badge evidence-${kind}`}>{KIND_LABEL[kind]}</span>
                  <span>{originLabel(c)}</span>
                  <span className="font-mono">{c.claim_id}</span>
                </span>
              </span>
              <ChevronRight className="mt-1 size-3.5 shrink-0" />
            </Button>
          );
        })}
      </div>
      {claims.length === 0 && (
        <p className="text-xs leading-5 text-muted-foreground">
          No claim read from a paper mentions this entry yet. That is not the same as no connection:
          it may simply not have been read.
        </p>
      )}
    </div>
  );
}
