import type { Metadata } from "next";
import Link from "next/link";
import { Public_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { SearchBox } from "@/components/SearchBox";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";

const serif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
const sans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TFOTB atlas",
  description: "Sourced connections between rare diseases, and honest gaps. Research support only.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} antialiased`}>
      <body className="min-h-screen bg-page">
        <EvidenceDrawerProvider>
          <header className="border-b border-rule bg-sheet">
            <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
              <Link href="/" className="font-serif text-xl font-semibold tracking-tight text-ink">
                TFOTB atlas
              </Link>
              <div className="min-w-[240px] flex-1">
                <SearchBox />
              </div>
              <span className="inline-flex items-center gap-2 text-sm text-muted">
                <span aria-hidden className="tape inline-block h-3 w-6 rounded-sm" />
                Synthetic demo data
              </span>
            </div>
          </header>
          {children}
          <footer className="mx-auto max-w-[1240px] px-4 py-10 text-sm text-muted">
            Research support only. Not a clinical system: no diagnosis, dosing, eligibility or
            treatment selection. Every statement links to its source.
          </footer>
        </EvidenceDrawerProvider>
      </body>
    </html>
  );
}
