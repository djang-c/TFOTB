import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowRight,
  BookOpenCheck,
  Database,
  FlaskConical,
  Network,
  ShieldCheck,
} from "lucide-react";
import { lazy, Suspense } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const DnaBackdrop = lazy(() =>
  import("@/components/DnaBackdrop").then((m) => ({ default: m.DnaBackdrop })),
);

export const Route = createFileRoute("/")({ ssr: false, component: Index });

const n = (v: number | undefined) => (v === undefined ? "—" : v.toLocaleString("en-US"));

function Index() {
  const navigate = useNavigate();
  const explore = (id: string) => void navigate({ to: "/explorer", search: { id } });
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 300_000, retry: 1 });
  const seeds = meta.data?.real?.seed ?? meta.data?.featured ?? [];
  const real = meta.data?.real;
  const store = meta.data?.store;
  const tiles = [
    {
      icon: Network,
      value: real ? n(real.counts.disease + real.counts.gene + real.counts.phenotype) : "—",
      label: "Catalogue entries",
      copy: real
        ? `${n(real.counts.disease)} diseases, ${n(real.counts.gene)} genes and ${n(real.counts.phenotype)} symptoms from pinned public ontologies (MONDO, HGNC, HPO).`
        : "Pinned public ontologies are not loaded on this server; only labelled demo entries are available.",
    },
    {
      icon: Database,
      value: n(store?.claims),
      label: "Claims read from papers",
      copy: store
        ? `From ${n(store.papers)} journal articles, each with its DOI link and the exact sentence. ${n(store.ai_hypotheses)} AI hypotheses and ${n(store.treatment_ideas)} treatment ideas are labelled as hypotheses.`
        : "Every claim cites the exact passage it came from.",
    },
    {
      icon: ShieldCheck,
      value: n(store?.terms_added),
      label: "Terms added by lookup",
      copy: "Search for something new and it is checked against NLM MeSH and Europe PMC. Verified terms join the catalogue; anything else stays on your device.",
    },
  ];
  return (
    <div>
      <section className="relative isolate flex min-h-[calc(100svh-64px)] flex-col items-center justify-center overflow-hidden border-b border-border px-5 py-20 text-center sm:px-8">
        <Suspense fallback={null}>
          <DnaBackdrop />
        </Suspense>
        <div
          className="hero-center-wash pointer-events-none absolute inset-0 z-[1]"
          aria-hidden="true"
        />
        <div className="relative z-20 mx-auto w-full max-w-[740px]">
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
          <CatalogSearch className="mx-auto mt-10 max-w-[600px] text-left" onSelect={explore} />
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <span className="mr-1 text-xs text-muted-foreground">Try</span>
            {seeds.slice(0, 4).map((s) => (
              <Button
                key={s.id}
                variant="outline"
                size="sm"
                className="rounded-full border-border bg-background/90 px-3 text-xs font-normal"
                onClick={() => explore(s.id)}
              >
                {s.label}
              </Button>
            ))}
            <Button
              asChild
              variant="outline"
              size="sm"
              className="rounded-full border-border bg-background/90 px-3 text-xs font-normal"
            >
              <Link to="/symptoms">No diagnosis yet? Describe symptoms</Link>
            </Button>
          </div>
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
      <section
        id="explore"
        className="mx-auto grid max-w-[1200px] gap-3 px-5 py-12 sm:px-8 md:grid-cols-3"
      >
        {tiles.map((t) => {
          const Icon = t.icon;
          return (
            <div key={t.label} className="rounded-lg border border-border/60 bg-muted/30 p-7">
              <Icon className="size-4 text-primary" />
              <div className="mt-8 font-mono text-2xl font-semibold">{t.value}</div>
              <h2 className="mt-2 text-sm font-semibold">{t.label}</h2>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{t.copy}</p>
            </div>
          );
        })}
      </section>
      <section className="mx-auto grid max-w-[1200px] gap-3 border-t border-border/60 px-5 py-12 sm:px-8 md:grid-cols-3">
        {[
          {
            icon: BookOpenCheck,
            title: "Every statement has a source",
            copy: "Claims quote the paper word for word and link its DOI. An AI found them, and the page says so. No human review is needed to be shown, and none is claimed.",
          },
          {
            icon: FlaskConical,
            title: "Hypotheses are labelled",
            copy: "AI hypotheses and treatment ideas are shown with their reasoning and the claims they were built from. They never count as evidence and are never advice.",
          },
          {
            icon: Network,
            title: "Gaps are stated, not hidden",
            copy: "When nothing is found the page says what was searched and when. It never says that no connection exists.",
          },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <div key={t.title}>
              <Icon className="size-4 text-primary" />
              <h2 className="mt-3 text-sm font-semibold">{t.title}</h2>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{t.copy}</p>
            </div>
          );
        })}
      </section>
      {seeds[0] && (
        <section className="mx-auto flex max-w-[1150px] flex-col gap-5 border-t border-border/60 px-5 py-12 sm:px-8 md:flex-row md:items-center">
          <div>
            <p className="section-kicker">Start here</p>
            <h2 className="mt-2 text-xl font-semibold">Open the {seeds[0].label} evidence graph</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              See related diseases and how strong the evidence is, open any claim to read its
              source, then replay the workflow simulation.
            </p>
          </div>
          <Button
            variant="outline"
            className="md:ml-auto"
            onClick={() => explore(seeds[0]?.id ?? "")}
          >
            Open graph <ArrowRight />
          </Button>
        </section>
      )}
    </div>
  );
}
