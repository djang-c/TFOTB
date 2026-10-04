import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowRight } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { Button } from "@/components/ui/button";
import { api, type EntityType } from "@/lib/api";
import { clean, REASON_ORDER, REASON_SHORT } from "@/lib/labels";
import { useMeta, useStarters } from "@/lib/queries";

const DnaBackdrop = lazy(() =>
  import("@/components/DnaBackdrop").then((m) => ({ default: m.DnaBackdrop })),
);

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "The Flight of the Buffalo — Rare Disease Connections" },
      {
        name: "description",
        content:
          "Search traceable rare-disease connections and inspect bounded robotics simulations.",
      },
      { property: "og:title", content: "The Flight of the Buffalo — Rare Disease Connections" },
      {
        property: "og:description",
        content:
          "Search traceable rare-disease connections and inspect bounded robotics simulations.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const n = (v: number | undefined) => (v === undefined ? "—" : v.toLocaleString("en-US"));

/** The design's hero artwork when its image file is present; otherwise the animated DNA drawing from the same design. */
function HeroArt() {
  const [missing, setMissing] = useState(false);
  if (missing)
    return (
      <Suspense fallback={null}>
        <DnaBackdrop />
      </Suspense>
    );
  return (
    <img
      src="/tfotb-scientific-hero.jpg"
      alt=""
      width={1920}
      height={1088}
      onError={() => setMissing(true)}
      className="absolute left-0 top-1/2 h-auto w-full -translate-y-1/2 object-contain"
      aria-hidden="true"
    />
  );
}

function Index() {
  const navigate = useNavigate();
  const explore = (id: string) => void navigate({ to: "/entity/$id", params: { id } });
  const { items: starters } = useStarters();
  const meta = useMeta();
  const real = meta.data?.real;
  const store = meta.data?.store;
  const terms = useQuery({ queryKey: ["terms"], queryFn: api.terms, staleTime: 60_000, retry: 0 });
  const examples = starters.filter((s) => s.type === "disease").slice(0, 3);
  const exampleData = useQueries({
    queries: examples.map((s) => ({
      queryKey: ["related-diseases", s.id],
      queryFn: () => api.relatedDiseases(s.id),
      staleTime: 300_000,
      retry: 0,
    })),
  });
  const entries = real
    ? real.counts.disease + real.counts.gene + real.counts.phenotype + (store?.terms_added ?? 0)
    : undefined;
  const metrics = [
    { value: n(entries), label: "Catalogue entries" },
    { value: n(store?.claims), label: "Claims read from papers" },
    { value: n(store?.papers), label: "Papers with claims" },
    { value: n(store?.terms_added), label: "Terms added by lookup" },
  ];
  const categories: {
    type: EntityType;
    label: string;
    copy: string;
    count: number | undefined;
    ids: { id: string; label: string }[];
  }[] = [
    {
      type: "disease",
      label: "Diseases",
      copy: "Conditions with linked genes, symptoms and mechanisms.",
      count: real?.counts.disease,
      ids: starters.filter((s) => s.type === "disease"),
    },
    {
      type: "gene",
      label: "Genes",
      copy: "Genes linked to disease in public reference files and in papers.",
      count: real?.counts.gene,
      ids: starters.filter((s) => s.type === "gene"),
    },
    {
      type: "phenotype",
      label: "Symptoms",
      copy: "Recorded symptoms, from the Human Phenotype Ontology.",
      count: real?.counts.phenotype,
      ids: [],
    },
    {
      type: "term",
      label: "Added by lookup",
      copy: "Medical terms verified against NLM MeSH or Europe PMC when someone searched for them.",
      count: store?.terms_added,
      ids: (terms.data?.items ?? []).slice(0, 3),
    },
  ];
  return (
    <div>
      {/* the artwork is clipped in its own layer, so the search dropdown may extend below the hero */}
      <section className="relative isolate flex min-h-[calc(100svh-64px)] flex-col items-center justify-center border-b border-border px-5 py-20 text-center sm:px-8">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          <HeroArt />
        </div>
        <div
          className="hero-center-wash pointer-events-none absolute inset-0 z-[1]"
          aria-hidden="true"
        />
        {/* above the "Explore" link (z-20) so the search dropdown is never covered by it */}
        <div className="relative z-30 mx-auto w-full max-w-[740px]">
          <img
            src="/logo.png"
            alt=""
            className="mx-auto mb-5 size-16 object-contain sm:size-[72px]"
            aria-hidden="true"
          />
          <h1 className="text-4xl font-semibold leading-tight sm:text-5xl">
            What are you looking into?
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-muted-foreground sm:text-base">
            A disease, a gene, a symptom or a mechanism. You get the research that connects to it,
            the source behind every statement, and an honest account of what is unknown.
          </p>
          <CatalogSearch
            unified
            className="mx-auto mt-10 max-w-[600px] text-left"
            onSelect={(entity) => explore(entity.id)}
          />
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <span className="mr-1 text-xs text-muted-foreground">Try</span>
            {starters.slice(0, 4).map(({ id, label }) => (
              <Button
                key={id}
                variant="outline"
                size="sm"
                className="rounded-full border-border bg-background/90 px-3 text-xs font-normal"
                onClick={() =>
                  window.dispatchEvent(new CustomEvent("search:fill", { detail: clean(label) }))
                }
              >
                {clean(label)}
              </Button>
            ))}
          </div>
          <Link
            to="/symptoms"
            className="mt-5 inline-block text-xs text-muted-foreground hover:text-primary"
          >
            No diagnosis yet? Describe symptoms to find candidate diseases →
          </Link>
          {meta.isError && (
            <p role="alert" className="mt-4 text-xs text-destructive">
              The API did not answer, so there is nothing to search yet.
            </p>
          )}
        </div>
        <a
          href="#explore"
          className="absolute bottom-6 z-20 flex flex-col items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary"
        >
          Not sure where to start? Explore <ArrowDown className="size-4" />
        </a>
      </section>

      <section id="explore" className="mx-auto max-w-[1200px] px-5 py-12 sm:px-8">
        <div className="grid grid-cols-2 gap-3 rounded-lg border border-border/60 bg-muted/30 p-6 sm:grid-cols-4">
          {metrics.map((m) => (
            <div key={m.label} className="text-center sm:text-left">
              <div className="font-mono text-2xl font-semibold">{m.value}</div>
              <div className="mt-1 text-xs text-muted-foreground">{m.label}</div>
            </div>
          ))}
        </div>

        {examples.length > 0 && (
          <div className="mt-12">
            <p className="section-kicker">Start here</p>
            <h2 className="mt-2 text-xl font-semibold">Example diseases</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              The rare diseases this project started from, picked by the project owner as examples.
              Open one to see every disease related to it and why.
            </p>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {examples.map((s, i) => {
                const r = exampleData[i]?.data;
                const pending = exampleData[i]?.isPending;
                return (
                  <Link
                    key={s.id}
                    to="/entity/$id"
                    params={{ id: s.id }}
                    className="group rounded-lg border border-border/60 bg-background p-6 transition-colors hover:border-primary/50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-semibold group-hover:text-primary">{clean(s.label)}</h3>
                      <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                    </div>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      {pending
                        ? "Finding related diseases…"
                        : !r
                          ? "Related diseases could not be loaded."
                          : r.none
                            ? "No similarities found in the data we hold."
                            : `${r.total} related diseases`}
                    </p>
                    {r && !r.none && (
                      <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                        {REASON_ORDER.filter((k) => r.counts[k]).map((k) => (
                          <span
                            key={k}
                            className="rounded-full border border-border/70 bg-muted/40 px-2 py-0.5"
                          >
                            {r.counts[k]} {REASON_SHORT[k]}
                          </span>
                        ))}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        <div className="mt-12 border-t border-border/60 pt-10">
          <p className="section-kicker">Browse the dataset</p>
          <h2 className="mt-2 text-xl font-semibold">By category</h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {categories.map(({ type, label, copy, count, ids }) => (
              <div key={type} className="rounded-lg border border-border/60 bg-muted/30 p-5">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold">{label}</h3>
                  <span className="font-mono text-xs text-muted-foreground">{n(count)}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{copy}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {ids.slice(0, 3).map((e) => (
                    <Link
                      key={e.id}
                      to="/entity/$id"
                      params={{ id: e.id }}
                      className="rounded-full border border-border/70 bg-background px-2 py-0.5 text-[11px] transition-colors hover:border-primary/50 hover:text-primary"
                    >
                      {clean(e.label)}
                    </Link>
                  ))}
                  {ids.length === 0 && (
                    <span className="text-[11px] text-muted-foreground">
                      {type === "term"
                        ? "None yet. Search for a new term to add one."
                        : "Search to browse."}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
