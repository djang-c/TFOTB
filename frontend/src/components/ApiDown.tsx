export function ApiDown({ what }: { what: string }) {
  return (
    <main className="mx-auto max-w-[680px] px-4 py-20">
      <p className="text-sm text-muted">Service unavailable</p>
      <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Could not load {what}.</h1>
      <p className="mt-2 text-[15px] text-muted">
        The data service did not answer. Nothing is wrong with your search: try again in a minute. If you
        are running the project locally, start the API with <code className="font-mono text-[13px]">make api</code> or
        check <code className="font-mono text-[13px]">NEXT_PUBLIC_API_BASE</code>.
      </p>
    </main>
  );
}
