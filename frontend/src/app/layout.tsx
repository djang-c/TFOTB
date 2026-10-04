import type { Metadata } from "next";
import Link from "next/link";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { HeaderSearch } from "@/components/HeaderSearch";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";

const sans = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "The Flight of the Buffalo",
  description: "Sourced connections between rare diseases, and honest gaps. Research support only.",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} antialiased`}>
      <body className="flex min-h-screen flex-col bg-page">
        <EvidenceDrawerProvider>
          <header className="sticky top-0 z-40 border-b border-rule bg-sheet/90 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4">
              <Link href="/" className="flex shrink-0 items-center gap-2.5 text-[15px] font-semibold tracking-tight text-ink hover:opacity-90 transition-opacity">
                <img src="/logo.png" alt="The Flight of the Buffalo Logo" className="h-7 w-7 object-contain rounded-sm" />
                <span>The Flight of the Buffalo</span>
              </Link>
              <div className="mx-auto w-full max-w-[560px]">
                <HeaderSearch />
              </div>
            </div>
          </header>
          <div className="flex-1">{children}</div>
          <footer className="mt-16 border-t border-rule">
            <div className="mx-auto flex max-w-[1240px] flex-wrap items-baseline justify-between gap-x-8 gap-y-2 px-4 py-6 text-xs text-muted">
              <p className="max-w-[72ch]">
                Research support only. Not a clinical system: no diagnosis, dosing, eligibility or
                treatment selection. Every statement links to its source.
              </p>
              <p className="flex items-center gap-2">
                <img src="/logo.png" alt="" className="h-4 w-4 object-contain opacity-70" />
                <span>The Flight of the Buffalo · Hack-Nation MVP</span>
              </p>
            </div>
          </footer>
        </EvidenceDrawerProvider>
      </body>
    </html>
  );
}
