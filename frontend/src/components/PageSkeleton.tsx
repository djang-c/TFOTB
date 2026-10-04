/** What a page looks like before its data arrives: the same shapes, softly pulsing, so a search lands somewhere
 *  instead of on a blank page. The real content then fades in over it. */
export function PageSkeleton({ label }: { label: string }) {
  const bar = (w: string, h = "h-3") => (
    <div className={`${h} ${w} animate-pulse rounded-full bg-muted-foreground/15`} />
  );
  return (
    <div role="status" aria-busy="true" aria-label={label} className="fade-in px-5 py-8 lg:px-10">
      <div className="space-y-3 border-b border-border pb-6">
        {bar("w-24")}
        {bar("w-2/3 max-w-xl", "h-7")}
        {bar("w-full max-w-3xl")}
        {bar("w-4/5 max-w-2xl")}
      </div>
      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="space-y-3 rounded-lg border border-border/60 bg-background/80 p-5"
          >
            {bar("w-1/3", "h-6")}
            {bar("w-2/3")}
          </div>
        ))}
      </div>
      <div className="mt-6 space-y-3 rounded-lg border border-border/60 bg-background/80 p-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center gap-4">
            {bar("w-1/4")}
            {bar("w-1/2")}
            {bar("w-12")}
          </div>
        ))}
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}
