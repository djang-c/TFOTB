import type { Metadata } from "next";
import Link from "next/link";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { HeaderSearch } from "@/components/HeaderSearch";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";
import { api } from "@/lib/api";

const sans = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "The Flight of the Buffalo",
  description: "Sourced connections between rare diseases, and honest gaps. Research support only.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // The synthetic marker follows the data: shown while any synthetic fixture is served.
  const synthetic = await api.meta()
    .then((m) => (m.counts_by_source_type.synthetic_fixture ?? 0) > 0)
    .catch(() => false);
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} antialiased`}>
      <body className="flex min-h-screen flex-col bg-page">
        <EvidenceDrawerProvider>
          <header className="sticky top-0 z-40 border-b border-rule bg-sheet/90 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4">
              <Link href="/" className="shrink-0 text-[15px] font-semibold tracking-tight text-ink">
                The Flight of the Buffalo
              </Link>
              <div className="mx-auto w-full max-w-[560px]">
                <HeaderSearch />
              </div>
              {synthetic && <span className="ml-auto hidden shrink-0 items-center gap-2 rounded-full border border-rule px-2.5 py-1 text-xs text-muted sm:inline-flex">
                <span aria-hidden className="tape inline-block h-2 w-2 rounded-full" />
                Synthetic data
              </span>}
            </div>
          </header>
          <div className="flex-1">{children}</div>
          <footer className="mt-16 border-t border-rule">
            <div className="mx-auto flex max-w-[1240px] flex-wrap items-baseline justify-between gap-x-8 gap-y-2 px-4 py-6 text-xs text-muted">
              <p className="max-w-[72ch]">
                Research support only. Not a clinical system: no diagnosis, dosing, eligibility or
                treatment selection. Every statement links to its source.
              </p>
              <p>The Flight of the Buffalo · Hack-Nation MVP</p>
            </div>
          </footer>
        </EvidenceDrawerProvider>
      </body>
    </html>
  );
}
