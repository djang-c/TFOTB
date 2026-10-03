"use client";

/** A suggested query chip: fills the large search box and opens its results. */
export function ExampleQuery({ q }: { q: string }) {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent("search:fill", { detail: q }))}
      className="rounded-full border border-rule px-3 py-1 text-ink/80 transition-colors hover:border-ink hover:text-ink"
    >
      {q}
    </button>
  );
}
