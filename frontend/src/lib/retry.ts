/** Hiccups on a small free host: a request can be refused while the one instance is waking up or busy (HTTP 429/503),
 *  and then a page's script or a data call fails once and works a moment later. These retry instead of showing an error. */

const RETRY_STATUS = new Set([429, 502, 503, 504]);
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** fetch that tries again on a refused or dropped request. Only for requests that are safe to repeat (GET). */
export async function fetchWithRetry(
  url: string,
  init?: RequestInit,
  { attempts = 4, baseMs = 600 }: { attempts?: number; baseMs?: number } = {},
): Promise<Response> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url, init);
      if (!RETRY_STATUS.has(res.status) || i === attempts - 1) return res;
    } catch (e) {
      last = e;
      if (i === attempts - 1) throw e;
    }
    await sleep(baseMs * 2 ** i);
  }
  throw last;
}

/** A lazily loaded page script that could not be fetched (a deploy changed it, or the host refused the request). */
export function isChunkError(error: unknown): boolean {
  const msg = error instanceof Error ? `${error.name} ${error.message}` : String(error);
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|ChunkLoadError/i.test(
    msg,
  );
}

const KEY = "tfotb.chunk-reload";
/** Reloads the page once (not in a loop) after a script failed to load. Returns true if it reloaded. */
export function reloadOnce(now = Date.now()): boolean {
  try {
    const last = Number(window.sessionStorage.getItem(KEY) ?? 0);
    if (now - last < 20_000) return false;
    window.sessionStorage.setItem(KEY, String(now));
  } catch {
    return false; // storage blocked: do not risk a reload loop
  }
  window.location.reload();
  return true;
}
