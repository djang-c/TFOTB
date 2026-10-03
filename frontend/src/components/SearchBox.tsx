"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Search } from "lucide-react";
import { api, enc, type EntityType } from "@/lib/api";

type Hit = { id: string; label: string; type: EntityType; synonyms: string[]; matched: string | null };

const PLACEHOLDER = "Search a disease, gene, symptom or mechanism";

export function SearchBox({ autoFocus = false, size = "sm" }: { autoFocus?: boolean; size?: "sm" | "lg" }) {
  const lg = size === "lg";
  const router = useRouter();
  const listId = useId();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [ambiguous, setAmbiguous] = useState(false);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const blurTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // "/" or Cmd/Ctrl+K focuses search from anywhere, unless the user is already typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && e.target.closest("input, textarea, [contenteditable]");
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    // Example chips on the home page fill the query and open the results.
    const onFill = (e: Event) => {
      clearTimeout(blurTimer.current);
      setQ((e as CustomEvent<string>).detail);
      setOpen(true);
      input.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("search:fill", onFill);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("search:fill", onFill);
    };
  }, []);

  useEffect(() => {
    if (!q.trim()) return;
    const t = setTimeout(() => {
      api.search(q)
        .then((r) => { setHits(r.results); setAmbiguous(!!r.ambiguous); setActive(0); setError(null); })
        .catch(() => setError("Search is unavailable. Check that the API is running."));
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  const go = (h: Hit) => { setOpen(false); setQ(""); router.push(`/entity/${enc(h.id)}`); };

  return (
    <div className="relative">
      <Search aria-hidden className={`pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted ${lg ? "left-4 h-5 w-5" : "left-2.5 h-4 w-4"}`} />
      <input
        ref={input}
        type="search"
        role="combobox"
        aria-expanded={open && hits.length > 0}
        aria-controls={listId}
        aria-activedescendant={open && hits[active] ? `${listId}-${active}` : undefined}
        aria-label="Search diseases, genes, phenotypes"
        autoFocus={autoFocus}
        value={q}
        placeholder={PLACEHOLDER}
        className={`w-full border border-rule placeholder:text-muted ${lg ? "h-14 rounded-xl bg-sheet pr-16 pl-12 text-base shadow-[0_1px_2px_rgba(17,24,39,0.04)]" : "h-9 rounded-md bg-subtle pr-12 pl-8 text-sm"} focus:border-link focus:bg-sheet focus:outline-none focus-visible:outline-none focus:ring-4 focus:ring-link/10 [&::-webkit-search-cancel-button]:hidden`}
        onChange={(e) => { setQ(e.target.value); setOpen(true); if (!e.target.value.trim()) setHits([]); }}
        onFocus={() => { clearTimeout(blurTimer.current); setOpen(true); }}
        onBlur={() => { blurTimer.current = setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && hits[active]) go(hits[active]);
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {!q && <kbd aria-hidden className={`pointer-events-none absolute hidden sm:inline top-1/2 -translate-y-1/2 ${lg ? "right-4" : "right-2.5"}`}>⌘K</kbd>}
      {open && q.trim() && (
        <div className="absolute z-30 mt-1.5 w-full overflow-hidden rounded-lg border border-rule bg-sheet shadow-[0_8px_24px_rgba(17,24,39,0.08)]">
          {error && <p className="px-3 py-3 text-sm text-fail">{error}</p>}
          {!error && hits.length === 0 && (
            <p className="px-3 py-3 text-sm text-muted">No matches for “{q}”. Try a synonym or an ID.</p>
          )}
          {hits.length > 0 && (
            <>
              <p className="px-3 pt-2.5 pb-1 text-xs text-muted">
                {hits.length} {hits.length === 1 ? "result" : "results"}
                {ambiguous && " · more than one could be what you mean"}
              </p>
              <ul id={listId} role="listbox" className="max-h-[360px] overflow-y-auto px-1.5 pb-1.5">
                {hits.map((h, i) => (
                  <li
                    key={h.id}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === active}
                    onMouseDown={() => go(h)}
                    onMouseEnter={() => setActive(i)}
                    className={`grid cursor-pointer grid-cols-[72px_minmax(0,1fr)] sm:grid-cols-[88px_minmax(0,1fr)_auto] items-baseline gap-3 rounded-md px-2 py-2 text-sm ${i === active ? "bg-subtle" : ""}`}
                  >
                    <span className="text-xs text-muted capitalize">{h.type}</span>
                    <span className="min-w-0 truncate">
                      <Highlight text={h.label} q={q} />
                      {h.matched && <span className="ml-2 text-muted">matches “{h.matched}”</span>}
                    </span>
                    <span className="hidden font-mono text-[11px] text-muted sm:inline">{h.id}</span>
                  </li>
                ))}
              </ul>
              <p className="flex gap-4 border-t border-rule bg-subtle px-3 py-1.5 text-[11px] text-muted" aria-hidden>
                <span><kbd>↑</kbd> <kbd>↓</kbd> move</span>
                <span><kbd>↵</kbd> open</span>
                <span><kbd>esc</kbd> close</span>
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Bolds the first case-insensitive occurrence of the query in a label. */
function Highlight({ text, q }: { text: string; q: string }) {
  const i = text.toLowerCase().indexOf(q.trim().toLowerCase());
  if (i < 0 || !q.trim()) return <span className="font-medium">{text}</span>;
  const n = q.trim().length;
  return (
    <span>
      {text.slice(0, i)}<span className="font-semibold">{text.slice(i, i + n)}</span>{text.slice(i + n)}
    </span>
  );
}
