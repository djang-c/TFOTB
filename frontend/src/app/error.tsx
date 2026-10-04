"use client";

import Link from "next/link";

export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <main className="mx-auto max-w-[680px] px-4 py-20">
      <p className="text-sm text-muted">Something went wrong</p>
      <h1 className="mt-1 text-[28px] font-semibold tracking-tight">This page could not be shown.</h1>
      <p className="mt-2 text-[15px] text-muted">
        An unexpected error stopped the page. No data was changed. Try again, or go back to the start page.
      </p>
      <p className="mt-6 flex gap-4 text-sm">
        <button onClick={() => retry()} className="rounded-md border border-rule px-3 py-1.5 hover:border-ink">Try again</button>
        <Link className="ref self-center" href="/">Start page</Link>
      </p>
    </main>
  );
}
