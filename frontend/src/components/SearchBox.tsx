"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { api, enc, type EntityType } from "@/lib/api";

type Hit = { id: string; label: string; type: EntityType; synonyms: string[]; matched: string | null };

export function SearchBox({ autoFocus = false }: { autoFocus?: boolean }) {
  const router = useRouter();
  const listId = useId();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!q.trim()) return;
    const t = setTimeout(() => {
      api.search(q)
        .then((r) => { setHits(r.results); setActive(0); setError(null); })
        .catch(() => setError("Search is unavailable. Check that the API is running."));
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  const go = (h: Hit) => { setOpen(false); setQ(""); router.push(`/entity/${enc(h.id)}`); };

  return (
    <div className="relative">
      <input
        type="search"
        role="combobox"
        aria-expanded={open && hits.length > 0}
        aria-controls={listId}
        aria-label="Search diseases, genes, phenotypes"
        autoFocus={autoFocus}
        value={q}
        placeholder="Search diseases, genes, variants, phenotypes"
        className="w-full rounded-md border border-rule bg-page px-3 py-2 text-[15px] placeholder:text-muted/80 focus:border-link focus:bg-white focus:outline-none"
        onChange={(e) => { setQ(e.target.value); setOpen(true); if (!e.target.value.trim()) setHits([]); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && hits[active]) go(hits[active]);
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && q.trim() && (
        <ul id={listId} role="listbox" className="absolute z-30 mt-1 w-full overflow-hidden rounded-md border border-rule bg-white shadow-lg">
          {error && <li className="px-3 py-2 text-sm text-fail">{error}</li>}
          {!error && hits.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted">Nothing indexed matches “{q}”. Try a synonym or an ID.</li>
          )}
          {hits.length > 1 && (
            <li className="border-b border-rule px-3 py-1.5 text-xs text-muted">{hits.length} matches. Pick the one you mean.</li>
          )}
          {hits.map((h, i) => (
            <li
              key={h.id}
              role="option"
              aria-selected={i === active}
              onMouseDown={() => go(h)}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 px-3 py-2 ${i === active ? "bg-link-soft" : ""}`}
            >
              <span>
                <span className="font-medium">{h.label}</span>
                {h.matched && <span className="ml-2 text-sm text-muted">also called {h.matched}</span>}
              </span>
              <span className="text-xs text-muted">{h.type}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
