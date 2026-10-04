import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Boxes, FileText, Network } from "lucide-react";
import { type ReactNode } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";
import { useFocusId } from "@/lib/focus";
import { HERO_STYLE } from "@/lib/heroStyle";
import { clean } from "@/lib/labels";
import { isLocalId } from "@/lib/localTerms";
import { useEntity } from "@/lib/queries";
import { STATUS_DOT, STATUS_TEXT, useApiStatus } from "@/lib/useApiStatus";

/** The pages that stand alone. The views of one search (dossier, graph, clusters) appear once a search is made. */
const PAGES = [
  { to: "/", label: "Home" },
  { to: "/symptoms", label: "Symptoms" },
  { to: "/simulation", label: "Simulation" },
  { to: "/10x", label: "10× case" },
] as const;

/** Ways to look at the entry being searched: shown only after a search. */
const VIEWS = [
  { key: "dossier", label: "Dossier", icon: FileText },
  { key: "graph", label: "Graph", icon: Network },
  { key: "clusters", label: "Clusters", icon: Boxes },
] as const;

/** Header row height plus the search row height, so full-screen pages (the graph) can fill exactly what is left. */
export const SHELL_OFFSET = "6.25rem";

/**
 * Layout: a bar across the top with the standing pages (Home, Symptoms, Simulation, 10× case) and the search. Once something has been
 * searched, a second row names it and offers the views of it: Dossier, Graph, Clusters.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <EvidenceDrawerProvider>
      <div className="relative min-h-screen bg-background text-foreground">
        {HERO_STYLE === "flow" && <div className="ambient-wash" aria-hidden="true" />}
        <div className="relative z-10">
          <TopBar />
          <ApiBanner />
          <main>{children}</main>
          <footer className="border-t border-border px-5 py-5 text-center text-[11px] leading-5 text-muted-foreground">
            Research support only. Not a clinical system: no diagnosis, dosing, eligibility or
            treatment advice. Nothing shown has been reviewed by an expert unless it says so.
          </footer>
        </div>
      </div>
    </EvidenceDrawerProvider>
  );
}

function TopBar() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const status = useApiStatus();
  const focusId = useFocusId();
  const searched = focusId && !isLocalId(focusId) ? focusId : null;
  const focus = useEntity(searched ?? "");
  const onGraph = path === "/explorer";
  const onClusters = path === "/clusters";
  const go = (id: string) => {
    if (onGraph) void navigate({ to: "/explorer", search: { id } });
    else if (onClusters) void navigate({ to: "/clusters", search: { id } });
    else void navigate({ to: "/entity/$id", params: { id } });
  };
  const standalone = PAGES.some((p) => p.to === path);
  const active = (key: (typeof VIEWS)[number]["key"]) =>
    (key === "dossier" && path.startsWith("/entity/")) ||
    (key === "graph" && onGraph) ||
    (key === "clusters" && onClusters);
  const tab = (on: boolean) =>
    `inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1 text-xs ${on ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`;
  return (
    <header className="app-header sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
        <Link to="/" className="flex shrink-0 items-center gap-2">
          <img src="/logo.png" alt="" className="size-8 object-contain" />
          <strong className="hidden text-sm font-semibold sm:inline">
            The Flight of the Buffalo
          </strong>
        </Link>
        <nav aria-label="Pages" className="flex items-center gap-1">
          {PAGES.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={`rounded-md px-3 py-1.5 text-sm ${path === to ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
              {label}
            </Link>
          ))}
        </nav>
        {path !== "/" && (
          <div className="ml-auto w-full max-w-sm">
            <CatalogSearch
              compact
              onSelect={(e) => go(e.id)}
              placeholder={
                onGraph
                  ? "Centre the graph on…"
                  : onClusters
                    ? "Clusters around…"
                    : "Search a disease, gene or symptom"
              }
            />
          </div>
        )}
        <span
          role="status"
          title={STATUS_TEXT[status]}
          className={`flex shrink-0 items-center gap-1.5 text-[10px] text-muted-foreground ${path === "/" ? "ml-auto" : ""}`}
        >
          <span className={`size-1.5 rounded-full ${STATUS_DOT[status]}`} />
          <span className="hidden xl:inline">{STATUS_TEXT[status]}</span>
        </span>
      </div>
      {searched && !standalone && (
        <div className="flex h-11 items-center gap-2 overflow-x-auto border-t border-border/60 px-4 lg:px-6">
          <span className="shrink-0 text-xs text-muted-foreground">Looking into</span>
          <strong className="max-w-[16rem] shrink-0 truncate text-xs font-semibold">
            {focus.data ? clean(focus.data.entity.label) : searched}
          </strong>
          <nav aria-label="Views of this search" className="ml-2 flex items-center gap-1">
            {VIEWS.map(({ key, label, icon: Icon }) => {
              const cls = tab(active(key));
              if (key === "dossier" && onGraph) return null; // the graph is its own view, not a door to the dossier
              if (key === "dossier")
                return (
                  <Link key={key} to="/entity/$id" params={{ id: searched }} className={cls}>
                    <Icon className="size-3.5" /> {label}
                  </Link>
                );
              return (
                <Link
                  key={key}
                  to={key === "graph" ? "/explorer" : "/clusters"}
                  search={{ id: searched }}
                  className={cls}
                >
                  <Icon className="size-3.5" /> {label}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </header>
  );
}

function ApiBanner() {
  const status = useApiStatus();
  if (status !== "down") return null;
  return (
    <div
      role="alert"
      className="border-b border-destructive/30 bg-destructive/5 px-5 py-3 text-center text-xs text-destructive"
    >
      The TFOTB API is not reachable, so nothing can be shown. Start it with{" "}
      <code className="font-mono">make api</code> (port 8000), or set{" "}
      <code className="font-mono">VITE_API_BASE</code> to where it runs.
    </div>
  );
}
