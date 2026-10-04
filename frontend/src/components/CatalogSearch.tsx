import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { LookupPanel } from "@/components/LookupPanel";
import { Button } from "@/components/ui/button";
import { api, type SearchHit } from "@/lib/api";
import { clean } from "@/lib/labels";
import { LOCAL_PREFIX, searchLocal, type LocalTerm } from "@/lib/localTerms";

const sections: [string, string][] = [
  ["disease", "Diseases"],
  ["gene", "Genes"],
  ["phenotype", "Symptoms"],
  ["mechanism", "Mechanisms"],
  ["drug", "Drugs"],
  ["variant", "Variants"],
  ["term", "Other terms"],
  ["asset", "Assets"],
  ["study", "Studies"],
  ["organization", "Organizations"],
];

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * Live search of the catalogue. Enter on something unknown starts a lookup against public medical sources
 * (see LookupPanel); typing alone never sends anything beyond the catalogue search to our own API.
 */
export function CatalogSearch({
  onSelect,
  compact = false,
  className = "",
  autoFocus = false,
}: {
  onSelect: (id: string) => void;
  compact?: boolean;
  className?: string;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [lookup, setLookup] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const term = useDebounced(query.trim(), 200);
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 300_000, retry: 1 });
  const found = useQuery({
    queryKey: ["search", term],
    queryFn: () => api.search(term),
    enabled: term.length >= 2,
    staleTime: 60_000,
    retry: 1,
  });
  const local = useMemo(() => (term.length >= 2 ? searchLocal(term) : []), [term]);
  const results: SearchHit[] = term.length >= 2 ? (found.data?.results ?? []) : [];
  const searching = term.length >= 2 && (found.isFetching || term !== query.trim());
  const starters = meta.data?.real?.seed ?? meta.data?.featured ?? [];

  useEffect(() => {
    const outside = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  const choose = (id: string) => {
    setQuery("");
    setOpen(false);
    setLookup(null);
    onSelect(id);
  };
  const chooseLocal = (t: LocalTerm) => choose(t.id);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const text = query.trim();
    if (text.length < 2) return;
    const fresh = await api
      .search(text)
      .then((r) => r.results)
      .catch(() => null);
    if (fresh === null) {
      setOpen(true);
      return;
    }
    const first = fresh[0] ?? searchLocal(text)[0];
    if (first) choose(first.id);
    else {
      setLookup(text);
      setOpen(true);
    }
  };

  return (
    <div ref={root} className={`relative ${className}`}>
      <form
        onSubmit={(e) => void submit(e)}
        role="search"
        className={`flex min-w-0 items-center border border-border bg-background focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10 ${compact ? "h-9 rounded-md px-2.5" : "h-12 rounded-full px-4"}`}
      >
        <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <input
          ref={input}
          autoFocus={autoFocus}
          aria-label="Search the catalogue"
          role="combobox"
          aria-expanded={open}
          aria-controls="catalog-results"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setLookup(null);
            setOpen(true);
          }}
          placeholder={
            compact ? "Search the catalogue" : "Search a disease, gene, symptom or mechanism"
          }
          className="min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground"
        />
        {searching && (
          <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Searching" />
        )}
        {!compact && !searching && (
          <kbd className="hidden shrink-0 rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
            ⌘K
          </kbd>
        )}
      </form>
      {open && (
        <div
          id="catalog-results"
          role="listbox"
          aria-label="Catalogue results"
          className="absolute inset-x-0 top-[calc(100%+5px)] z-30 max-h-[28rem] overflow-y-auto rounded-md border border-border bg-popover text-left shadow-md"
        >
          {lookup ? (
            <LookupPanel term={lookup} onOpen={choose} onOpenLocal={chooseLocal} />
          ) : term.length < 2 ? (
            <div>
              <div className="border-b border-border bg-muted px-3 py-1.5 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                Start with
              </div>
              {starters.map((s) => (
                <Option key={s.id} id={s.id} label={s.label} type={s.type} onChoose={choose} />
              ))}
              <p className="px-3 py-3 text-[11px] leading-4 text-muted-foreground">
                Type a disease, gene, symptom or mechanism. Press Enter on something new to check it
                against public medical sources.
              </p>
            </div>
          ) : (
            <>
              {sections.map(([type, label]) => {
                const rows = results.filter((e) => e.type === type);
                return rows.length ? (
                  <div key={type}>
                    <div className="sticky top-0 border-b border-border bg-muted px-3 py-1.5 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                      {label} <span className="ml-1 font-normal">{rows.length}</span>
                    </div>
                    {rows.map((e) => (
                      <Option
                        key={e.id}
                        id={e.id}
                        label={e.label}
                        type={e.type}
                        note={
                          e.added_by_lookup
                            ? "added by lookup"
                            : e.matched && e.matched !== e.label
                              ? `matched “${e.matched}”`
                              : undefined
                        }
                        onChoose={choose}
                      />
                    ))}
                  </div>
                ) : null;
              })}
              {local.length > 0 && (
                <div>
                  <div className="border-b border-border bg-muted px-3 py-1.5 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                    On this device only
                  </div>
                  {local.map((t) => (
                    <Option
                      key={t.id}
                      id={t.id}
                      label={t.label}
                      type="term"
                      note="local, unverified"
                      onChoose={choose}
                    />
                  ))}
                </div>
              )}
              {!searching && found.isSuccess && results.length === 0 && local.length === 0 && (
                <div className="px-3 py-4 text-xs text-muted-foreground">
                  No entry for “{term}”. Press{" "}
                  <kbd className="rounded border border-border px-1 font-mono">Enter</kbd> to check
                  it against public medical sources.
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-3 block"
                    onClick={() => setLookup(term)}
                  >
                    Check “{term}” now
                  </Button>
                </div>
              )}
              {found.isError && (
                <p role="alert" className="px-3 py-4 text-xs text-destructive">
                  The catalogue could not be searched. Check that the API is running.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Option({
  id,
  label,
  type,
  note,
  onChoose,
}: {
  id: string;
  label: string;
  type: string;
  note?: string | undefined;
  onChoose: (id: string) => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      role="option"
      aria-selected="false"
      onClick={() => onChoose(id)}
      className="h-auto min-h-9 w-full justify-start rounded-none px-3 py-2 text-left font-normal"
    >
      <span className={`size-2 shrink-0 rounded-full entity-dot-${type}`} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-xs">{clean(label)}</span>
        {note && <span className="block text-[10px] text-muted-foreground">{note}</span>}
      </span>
      <code className="truncate text-[10px] text-muted-foreground">
        {id.startsWith(LOCAL_PREFIX) ? "local" : id}
      </code>
    </Button>
  );
}
