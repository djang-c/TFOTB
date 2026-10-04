import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Boxes, Cpu, Home, Menu, Network, Stethoscope, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { useFocusId } from "@/lib/focus";
import { clean } from "@/lib/labels";
import { useEntity, useStarters } from "@/lib/queries";
import { STATUS_DOT, STATUS_TEXT, useApiStatus } from "@/lib/useApiStatus";

const PAGES = [
  { to: "/", label: "Home", icon: Home, follows: false },
  { to: "/explorer", label: "Graph", icon: Network, follows: true },
  { to: "/clusters", label: "Clusters", icon: Boxes, follows: true },
  { to: "/symptoms", label: "Symptoms", icon: Stethoscope, follows: false },
  { to: "/simulation", label: "Simulation", icon: Cpu, follows: false },
] as const;

/**
 * Layout: a vertical catalogue bar on the left (one search, the pages, the entry being looked into, entries to start
 * from) and the page on the right. The one search box opens the dossier, except on the Graph and Clusters pages,
 * where it re-centres that page on what was found.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <EvidenceDrawerProvider>
      <div className="min-h-screen bg-background text-foreground lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside
          className="sticky top-0 hidden h-screen overflow-y-auto border-r border-border bg-card lg:block"
          aria-label="Catalogue"
        >
          <Sidebar onNavigate={() => {}} />
        </aside>
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur-md lg:hidden">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo.png" alt="" className="size-8 object-contain" />
            <strong className="text-sm font-semibold">The Flight of the Buffalo</strong>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto"
            onClick={() => setOpen(!open)}
            aria-label={open ? "Close the catalogue" : "Open the catalogue"}
          >
            {open ? <X /> : <Menu />}
          </Button>
        </header>
        {open && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="absolute inset-0 bg-foreground/20"
              onClick={() => setOpen(false)}
              aria-hidden="true"
            />
            <aside
              className="absolute inset-y-0 left-0 w-[280px] overflow-y-auto border-r border-border bg-card"
              aria-label="Catalogue"
            >
              <Sidebar onNavigate={() => setOpen(false)} />
            </aside>
          </div>
        )}
        <div className="min-w-0">
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

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const status = useApiStatus();
  const focusId = useFocusId();
  const focus = useEntity(focusId ?? "");
  const { items: starters } = useStarters();
  const focusLabel = focus.data ? clean(focus.data.entity.label) : focusId;
  const onGraph = path === "/explorer";
  const onClusters = path === "/clusters";
  const go = (id: string) => {
    onNavigate();
    if (onGraph) void navigate({ to: "/explorer", search: { id } });
    else if (onClusters) void navigate({ to: "/clusters", search: { id } });
    else void navigate({ to: "/entity/$id", params: { id } });
  };
  const linkClass = (active: boolean) =>
    `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm ${active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`;
  return (
    <div className="flex min-h-full flex-col gap-6 p-4">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-3 px-1">
        <img src="/logo.png" alt="" className="size-9 object-contain" />
        <strong className="text-sm font-semibold leading-tight">The Flight of the Buffalo</strong>
      </Link>

      {path !== "/" && (
        <CatalogSearch
          compact
          onSelect={(e) => go(e.id)}
          placeholder={
            onGraph
              ? "Centre the graph on…"
              : onClusters
                ? "Clusters around…"
                : "Search the catalogue"
          }
        />
      )}

      <nav aria-label="Pages">
        <p className="section-kicker px-2.5 pb-1.5">Pages</p>
        {PAGES.map(({ to, label, icon: Icon, follows }) => {
          const active = to === "/" ? path === "/" : path.startsWith(to);
          return follows && focusId ? (
            <Link
              key={to}
              to={to}
              search={{ id: focusId }}
              onClick={onNavigate}
              className={linkClass(active)}
            >
              <Icon className="size-4" /> {label}
            </Link>
          ) : (
            <Link key={to} to={to} onClick={onNavigate} className={linkClass(active)}>
              <Icon className="size-4" /> {label}
            </Link>
          );
        })}
      </nav>

      {focusId && !focusId.startsWith("LOCAL:") && (
        <section aria-label="Looking into">
          <p className="section-kicker px-2.5 pb-1.5">Looking into</p>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium leading-5">{focusLabel}</p>
            <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{focusId}</p>
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              {!onGraph && (
                <Link
                  to="/entity/$id"
                  params={{ id: focusId }}
                  onClick={onNavigate}
                  className="rounded-full border border-border px-2 py-0.5 hover:border-primary/50 hover:text-primary"
                >
                  Dossier
                </Link>
              )}
              <Link
                to="/explorer"
                search={{ id: focusId }}
                onClick={onNavigate}
                className="rounded-full border border-border px-2 py-0.5 hover:border-primary/50 hover:text-primary"
              >
                Graph
              </Link>
              <Link
                to="/clusters"
                search={{ id: focusId }}
                onClick={onNavigate}
                className="rounded-full border border-border px-2 py-0.5 hover:border-primary/50 hover:text-primary"
              >
                Clusters
              </Link>
            </div>
          </div>
        </section>
      )}

      {starters.length > 0 && (
        <section aria-label="Start with">
          <p className="section-kicker px-2.5 pb-1.5">Seed cluster</p>
          {starters.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => go(s.id)}
              className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <span className={`size-2 shrink-0 rounded-full entity-dot-${s.type}`} />
              <span className="min-w-0 flex-1 truncate">{clean(s.label)}</span>
              <span className="text-[10px] capitalize">{s.type}</span>
            </button>
          ))}
        </section>
      )}

      <p
        role="status"
        className="mt-auto flex items-center gap-2 px-2.5 text-[10px] text-muted-foreground"
      >
        <span className={`size-1.5 rounded-full ${STATUS_DOT[status]}`} />
        {STATUS_TEXT[status]}
      </p>
    </div>
  );
}
