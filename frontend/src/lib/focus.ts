import { useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";

// The entry the visitor is looking into. Searching sets it; the Graph and Clusters pages follow it, so every tab is
// about the same search. Kept in this browser only (a convenience, never shared); storage may be blocked.
const KEY = "tfotb.focus.v1";

function read(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function write(id: string) {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    /* storage blocked: the focus still follows the address bar */
  }
}

/** The entry named in the address bar (dossier path or `?id=`), else the last one looked at. */
export function useFocusId(): string | null {
  const loc = useRouterState({ select: (s) => s.location });
  const fromPath = /^\/entity\/(.+)$/.exec(loc.pathname)?.[1];
  const search = loc.search as { id?: unknown };
  const fromSearch = typeof search.id === "string" ? search.id : undefined;
  const current = fromPath ? decodeURIComponent(fromPath) : fromSearch;
  // Read after the first render: the prerendered page shell has no browser storage, and both renders must match.
  const [last, setLast] = useState<string | null>(null);
  useEffect(() => {
    setLast((v) => v ?? read());
  }, []);
  useEffect(() => {
    if (current && !current.startsWith("LOCAL:") && current !== last) {
      write(current);
      setLast(current);
    }
  }, [current, last]);
  return current ?? last;
}
