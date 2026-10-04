import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-[680px] px-4 py-20">
      <p className="text-sm text-muted">Not found</p>
      <h1 className="mt-1 text-[28px] font-semibold tracking-tight">There is no entry at this address.</h1>
      <p className="mt-2 text-[15px] text-muted">
        The identifier may be mistyped, retired in a newer release of the source files, or not indexed here.
        Use the search at the top: names, synonyms, gene symbols and identifiers all work.
      </p>
      <p className="mt-6 text-sm"><Link className="ref" href="/">Back to the start page</Link></p>
    </main>
  );
}
