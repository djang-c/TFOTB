import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export function Section({
  title,
  count,
  children,
  tone = "",
}: {
  title: string;
  count?: number | string | undefined;
  children: ReactNode;
  tone?: string;
}) {
  return (
    <section className={`border-b border-border p-6 ${tone}`}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {count !== undefined && (
          <span className="font-mono text-[10px] text-muted-foreground">{count}</span>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => (
  <p className="text-xs leading-5 text-muted-foreground">{children}</p>
);

/** Shows the first few items; the rest sit behind one button. */
export function Reveal<T>({
  items,
  first,
  noun,
  render,
}: {
  items: T[];
  first: number;
  noun: string;
  render: (xs: T[]) => ReactNode;
}) {
  const [all, setAll] = useState(false);
  if (items.length <= first + 1 || all) return <>{render(items)}</>;
  return (
    <>
      {render(items.slice(0, first))}
      <Button
        variant="ghost"
        size="sm"
        className="mt-2 text-xs text-primary"
        onClick={() => setAll(true)}
      >
        Show all {items.length} {noun}
      </Button>
    </>
  );
}
