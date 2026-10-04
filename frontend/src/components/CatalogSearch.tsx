import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { LookupPanel } from "@/components/LookupPanel";
import { api, type SearchHit } from "@/lib/api";
import { clean } from "@/lib/labels";
import { LOCAL_PREFIX, searchLocal, type LocalTerm } from "@/lib/localTerms";
import { useStarters } from "@/lib/queries";

const PLACEHOLDER = "Search a disease, gene, symptom or mechanism";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * The design's search box, reading the live catalogue. Arrow keys and Enter work as designed. Pressing Enter on
 * something the catalogue has never seen checks it against public medical sources (see LookupPanel); typing alone
 * never sends anything beyond the search of our own API.
 */
export function CatalogSearch({
  onSelect,
  compact = false,
  className = "",
  autoFocus = false,
}: {
  onSelect: (entity: Pick<SearchHit, "id" | "label" | "type">) => void;
  compact?: boolean;
  unified?: boolean;
  className?: string;
  autoFocus?: boolean;
}) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [lookup, setLookup] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const blurTimer = useRef<number | undefined>(undefined);
  const term = useDebounced(query.trim(), 200);
  const { items: starters } = useStarters();
  const found = useQuery({
    queryKey: ["search", term],
    queryFn: () => api.search(term),
    enabled: term.length >= 2,
    staleTime: 60_000,
    retry: 1,
  });
  const localHits: SearchHit[] =
    term.length >= 2
      ? searchLocal(term).map((t) => ({
          id: t.id,
          label: t.label,
          type: "term",
          matched: null,
          match: "local",
        }))
      : [];
  const results: SearchHit[] =
    term.length >= 2 ? [...(found.data?.results ?? []), ...localHits] : [];
  const ambiguous = Boolean(found.data?.ambiguous);
  const searching = term.length >= 2 && (found.isFetching || term !== query.trim());

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing =
        event.target instanceof HTMLElement &&
        Boolean(event.target.closest("input, textarea, [contenteditable]"));
      if (
        (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) ||
        (event.key === "/" && !typing)
      ) {
        event.preventDefault();
        input.current?.focus();
      }
    };
    const onFill = (event: Event) => {
      const next = (event as CustomEvent<string>).detail;
      if (typeof next !== "string") return;
      if (blurTimer.current) window.clearTimeout(blurTimer.current);
      setQuery(next);
      setActive(0);
      setLookup(null);
      setOpen(true);
      input.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("search:fill", onFill);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("search:fill", onFill);
      if (blurTimer.current) window.clearTimeout(blurTimer.current);
    };
  }, []);

  const choose = (entity: Pick<SearchHit, "id" | "label" | "type">) => {
    setOpen(false);
    setQuery("");
    setLookup(null);
    onSelect(entity);
  };
  const chooseId = (id: string) => choose({ id, label: id, type: "term" });
  const chooseLocal = (t: LocalTerm) => chooseId(t.id);
  const showList = open && !lookup && query.trim().length > 0;

  const onEnter = async () => {
    const text = query.trim();
    if (text.length < 2) return;
    if (results[active] && !searching) return choose(results[active]);
    // Nothing in view yet (typed fast, or nothing matches): ask the API now, then open the best match or look the term up.
    const fresh = await api
      .search(text)
      .then((r) => r.results)
      .catch(() => null);
    if (fresh === null) return setOpen(true);
    const first = fresh[0] ?? searchLocal(text)[0];
    if (first)
      return choose({
        id: first.id,
        label: first.label,
        type: "type" in first ? first.type : "term",
      });
    setLookup(text);
    setOpen(true);
  };

  return (
    <div className={`relative ${className}`}>
      <Search
        aria-hidden="true"
        className={`pointer-events-none absolute top-1/2 z-10 -translate-y-1/2 text-muted-foreground ${compact ? "left-2.5 size-4" : "left-4 size-5"}`}
      />
      <input
        ref={input}
        type="search"
        role="combobox"
        aria-label={PLACEHOLDER}
        aria-expanded={open && Boolean(query.trim())}
        aria-controls={showList ? listId : undefined}
        aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
        autoFocus={autoFocus}
        value={query}
        placeholder={compact ? "Search the catalog" : PLACEHOLDER}
        className={`w-full border border-border/70 bg-background placeholder:text-muted-foreground focus:border-primary focus:bg-background focus:outline-none focus:ring-4 focus:ring-primary/10 [&::-webkit-search-cancel-button]:hidden ${compact ? "h-9 rounded-md pr-12 pl-8 text-sm" : "h-14 rounded-xl pr-16 pl-12 text-base shadow-sm"}`}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
          setLookup(null);
          setOpen(true);
        }}
        onFocus={() => {
          if (blurTimer.current) window.clearTimeout(blurTimer.current);
          setOpen(true);
        }}
        onBlur={() => {
          blurTimer.current = window.setTimeout(() => setOpen(false), 160);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((c) => Math.min(c + 1, Math.max(0, results.length - 1)));
          }
          if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((c) => Math.max(c - 1, 0));
          }
          if (event.key === "Enter") {
            event.preventDefault();
            void onEnter();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
          }
        }}
      />
      {searching ? (
        <Loader2
          aria-label="Searching"
          className={`absolute top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground ${compact ? "right-2.5" : "right-4"}`}
        />
      ) : (
        !query && (
          <kbd
            aria-hidden="true"
            className={`pointer-events-none absolute top-1/2 hidden -translate-y-1/2 rounded border border-border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground sm:inline ${compact ? "right-2.5" : "right-4"}`}
          >
            ⌘K
          </kbd>
        )
      )}

      {open && !query.trim() && starters.length > 0 && (
        <div className="absolute z-30 mt-1.5 w-full overflow-hidden rounded-lg border border-border bg-popover text-left shadow-lg">
          <p className="px-3 pt-2.5 pb-1 text-xs text-muted-foreground">Start with</p>
          <ul className="px-1.5 pb-1.5">
            {starters.map((s) => (
              <li
                key={s.id}
                role="option"
                aria-selected="false"
                onMouseDown={() => choose(s)}
                className="grid cursor-pointer grid-cols-[72px_minmax(0,1fr)] items-baseline gap-3 rounded-md px-2 py-2 text-sm hover:bg-muted sm:grid-cols-[88px_minmax(0,1fr)_auto]"
              >
                <span className="text-xs capitalize text-muted-foreground">{s.type}</span>
                <span className="min-w-0 truncate font-medium">{clean(s.label)}</span>
                <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
                  {s.id}
                </span>
              </li>
            ))}
          </ul>
          <p className="border-t border-border bg-muted px-3 py-1.5 text-[11px] text-muted-foreground">
            Press Enter on something new to check it against public medical sources.
          </p>
        </div>
      )}

      {open && lookup && (
        <div
          className="absolute z-30 mt-1.5 w-full overflow-hidden rounded-lg border border-border bg-popover text-left shadow-lg"
          onMouseDown={(e) => e.preventDefault()}
        >
          <LookupPanel term={lookup} onOpen={chooseId} onOpenLocal={chooseLocal} />
        </div>
      )}

      {showList && (
        <div className="absolute z-30 mt-1.5 w-full overflow-hidden rounded-lg border border-border bg-popover text-left shadow-lg">
          {found.isError ? (
            <p role="alert" className="px-3 py-3 text-sm text-destructive">
              The catalogue could not be searched. Check that the API is running.
            </p>
          ) : results.length === 0 ? (
            searching ? (
              <p className="px-3 py-3 text-sm text-muted-foreground">Searching…</p>
            ) : (
              <div className="px-3 py-3 text-sm text-muted-foreground">
                No matches for “{query}”. Press{" "}
                <kbd className="rounded border border-border px-1 font-mono">Enter</kbd> to check it
                against public medical sources.
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setLookup(query.trim());
                  }}
                  className="mt-2 block rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-muted"
                >
                  Check “{query.trim()}” now
                </button>
              </div>
            )
          ) : (
            <>
              <p className="px-3 pt-2.5 pb-1 text-xs text-muted-foreground">
                {results.length} {results.length === 1 ? "result" : "results"}
                {ambiguous && " · this name is used by more than one entry"}
              </p>
              <ul
                id={listId}
                role="listbox"
                aria-label="Entity catalog"
                className="max-h-[360px] overflow-y-auto px-1.5 pb-1.5"
              >
                {results.map((entity, index) => (
                  <li
                    key={entity.id}
                    id={`${listId}-${index}`}
                    role="option"
                    aria-selected={index === active}
                    onMouseDown={() => choose(entity)}
                    onMouseEnter={() => setActive(index)}
                    className={`grid cursor-pointer grid-cols-[72px_minmax(0,1fr)] items-baseline gap-3 rounded-md px-2 py-2 text-sm sm:grid-cols-[88px_minmax(0,1fr)_auto] ${index === active ? "bg-muted" : ""}`}
                  >
                    <span className="text-xs capitalize text-muted-foreground">{entity.type}</span>
                    <span className="min-w-0 truncate">
                      <Highlight text={clean(entity.label)} query={query} />
                      {entity.source_type === "synthetic_fixture" && (
                        <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[11px] text-foreground">
                          Synthetic
                        </span>
                      )}
                      {entity.added_by_lookup && (
                        <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[11px] text-foreground">
                          added by lookup
                        </span>
                      )}
                      {entity.id.startsWith(LOCAL_PREFIX) && (
                        <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[11px] text-foreground">
                          this device only
                        </span>
                      )}
                      {entity.matched && entity.matched !== entity.label && (
                        <span className="ml-2 text-[11px] text-muted-foreground">
                          matched “{entity.matched}”
                        </span>
                      )}
                    </span>
                    <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
                      {entity.id.startsWith(LOCAL_PREFIX) ? "local" : entity.id}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="flex items-center gap-4 border-t border-border bg-muted px-3 py-1.5 text-[11px] text-muted-foreground">
                <span>
                  <kbd>↑</kbd> <kbd>↓</kbd> move
                </span>
                <span>
                  <kbd>↵</kbd> open
                </span>
                <span>
                  <kbd>esc</kbd> close
                </span>
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Highlight({ text, query }: { text: string; query: string }) {
  const needle = query.trim();
  const index = text.toLowerCase().indexOf(needle.toLowerCase());
  if (index < 0 || !needle) return <span className="font-medium">{text}</span>;
  return (
    <span>
      {text.slice(0, index)}
      <span className="font-semibold">{text.slice(index, index + needle.length)}</span>
      {text.slice(index + needle.length)}
    </span>
  );
}
