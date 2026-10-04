import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Menu, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { useApiStatus, STATUS_TEXT, STATUS_DOT } from "@/lib/useApiStatus";

const nav = [
  { to: "/", label: "Overview" },
  { to: "/explorer", label: "Graph" },
  { to: "/symptoms", label: "Symptoms" },
  { to: "/clusters", label: "Clusters" },
  { to: "/simulation", label: "Simulation" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const status = useApiStatus();
  return (
    <EvidenceDrawerProvider>
      <div className="min-h-screen bg-background text-foreground">
        <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-md">
          <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
            <Link
              to="/"
              className="flex shrink-0 items-center gap-3"
              onClick={() => setOpen(false)}
            >
              <img src="/logo.png" alt="" className="size-9 object-contain" />
              <strong className="max-w-[190px] text-xs font-semibold leading-tight sm:max-w-none sm:text-sm">
                The Flight of the Buffalo
              </strong>
            </Link>
            {path !== "/" && (
              <CatalogSearch
                compact
                className="mx-auto hidden w-full max-w-md md:block"
                onSelect={(id) => void navigate({ to: "/explorer", search: { id } })}
              />
            )}
            <nav
              className="ml-auto hidden h-full items-center gap-5 md:flex"
              aria-label="Primary navigation"
            >
              {nav.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex h-full items-center border-b text-xs font-medium ${path === item.to ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <span
              role="status"
              className="hidden shrink-0 items-center gap-2 border-l border-border pl-4 text-[10px] text-muted-foreground lg:flex"
            >
              <span className={`size-1.5 rounded-full ${STATUS_DOT[status]}`} />
              {STATUS_TEXT[status]}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto md:hidden"
              onClick={() => setOpen(!open)}
              aria-label={open ? "Close navigation" : "Open navigation"}
            >
              {open ? <X /> : <Menu />}
            </Button>
          </div>
          {open && (
            <nav className="border-t border-border bg-background px-4 py-3 md:hidden">
              <CatalogSearch
                compact
                className="mb-2"
                onSelect={(id) => {
                  setOpen(false);
                  void navigate({ to: "/explorer", search: { id } });
                }}
              />
              {nav.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className="block border-b border-border py-3 text-sm last:border-0"
                >
                  {item.label}
                </Link>
              ))}
              <div className="pt-3 text-xs text-muted-foreground">{STATUS_TEXT[status]}</div>
            </nav>
          )}
        </header>
        {status === "down" && <ApiDown />}
        <main>{children}</main>
        <footer className="border-t border-border px-5 py-6 text-center text-[11px] leading-5 text-muted-foreground">
          Research support only. Not a clinical system: no diagnosis, dosing, eligibility or
          treatment advice. Nothing shown has been reviewed by an expert unless it says so.
        </footer>
      </div>
    </EvidenceDrawerProvider>
  );
}

export function ApiDown() {
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
