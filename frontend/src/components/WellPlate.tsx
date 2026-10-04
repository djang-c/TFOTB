import { firstWorkflowStep, type WorkflowStep } from "@/lib/simulation";

const rows = "ABCDEFGH".split("");
export function WellPlate({
  step,
  steps = [firstWorkflowStep],
}: {
  step: number;
  steps?: WorkflowStep[];
}) {
  const active = new Set(steps.slice(0, step + 1).flatMap((item) => item.wells));
  const current = new Set(steps[step]?.wells ?? []);
  return (
    <div className="mx-auto w-full max-w-3xl border border-border bg-plate p-3 sm:p-5">
      <div className="grid grid-cols-[18px_repeat(12,minmax(18px,1fr))] gap-1.5 sm:gap-2">
        <span />
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className="text-center font-mono text-[9px] text-muted-foreground">
            {i + 1}
          </span>
        ))}
        {rows.flatMap((row) => [
          <span
            key={`${row}-label`}
            className="flex items-center font-mono text-[9px] text-muted-foreground"
          >
            {row}
          </span>,
          ...Array.from({ length: 12 }, (_, i) => {
            const id = `${row}${i + 1}`;
            return (
              <div
                key={id}
                title={`Well ${id}`}
                className={`aspect-square rounded-full border transition-all duration-500 ${current.has(id) ? "scale-110 border-primary bg-primary shadow-[0_0_0_3px_var(--well-ring)]" : active.has(id) ? "border-primary/40 bg-primary/35" : "border-border bg-background"}`}
              />
            );
          }),
        ])}
      </div>
    </div>
  );
}
