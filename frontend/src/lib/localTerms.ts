// Terms the public vocabularies could not verify are kept only on this device (localStorage). They are never sent to
// the shared catalogue and never leave the browser. Every access is guarded: storage can be blocked or full.

export interface LocalTerm {
  id: string;
  label: string;
  note: string;
  created: string;
  /** Why it is local: the verification verdict, or "unavailable" when the public services could not be reached. */
  reason: string;
}

const KEY = "tfotb.localTerms.v1";
export const LOCAL_PREFIX = "LOCAL:";

const slugOf = (text: string) =>
  text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60) || "term";

export function listLocal(): LocalTerm[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "[]") as unknown;
    return Array.isArray(raw)
      ? raw.filter(
          (x): x is LocalTerm =>
            !!x &&
            typeof x === "object" &&
            typeof (x as LocalTerm).id === "string" &&
            typeof (x as LocalTerm).label === "string",
        )
      : [];
  } catch {
    return [];
  }
}

function write(items: LocalTerm[]): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items.slice(-200)));
    return true;
  } catch {
    return false;
  }
}

export const isLocalId = (id: string) => id.startsWith(LOCAL_PREFIX);
export const getLocal = (id: string) => listLocal().find((t) => t.id === id) ?? null;

export function saveLocal(label: string, reason: string): LocalTerm {
  const id = `${LOCAL_PREFIX}${slugOf(label)}`;
  const have = getLocal(id);
  if (have) return have;
  const term: LocalTerm = {
    id,
    label: label.trim().slice(0, 80),
    note: "",
    created: new Date().toISOString().slice(0, 10),
    reason,
  };
  write([...listLocal(), term]);
  return term;
}

export function updateNote(id: string, note: string): void {
  write(listLocal().map((t) => (t.id === id ? { ...t, note: note.slice(0, 2000) } : t)));
}

export function removeLocal(id: string): void {
  write(listLocal().filter((t) => t.id !== id));
}

/** Local terms whose name matches what the visitor is typing, for the search dropdown. */
export function searchLocal(query: string): LocalTerm[] {
  const q = query.trim().toLowerCase();
  return q
    ? listLocal()
        .filter((t) => t.label.toLowerCase().includes(q))
        .slice(0, 5)
    : [];
}
