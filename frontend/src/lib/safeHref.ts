/**
 * Only http(s) addresses may become links. A source or registry URL can come from a database record, a paper
 * or an upload, so a `javascript:` or `data:` address must never be rendered as a clickable link.
 * Returns the normalised URL, or undefined when it is not a plain web address.
 */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : undefined;
  } catch {
    return undefined;
  }
}
