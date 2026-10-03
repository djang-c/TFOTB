export function ApiDown({ what }: { what: string }) {
  return (
    <main className="mx-auto max-w-[1240px] px-4 py-16">
      <h1 className="text-2xl font-semibold">Could not load {what}</h1>
      <p className="mt-2 text-muted">
        The API did not answer. Start it with <code>make api</code>, or check
        NEXT_PUBLIC_API_BASE, then reload this page.
      </p>
    </main>
  );
}
