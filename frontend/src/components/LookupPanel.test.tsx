import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LookupPanel } from "@/components/LookupPanel";
import { listLocal } from "@/lib/localTerms";
import { mockApi } from "@/test/fixtures";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));

const wrap = (ui: React.ReactElement) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {ui}
    </QueryClientProvider>,
  );
beforeEach(() => window.localStorage.clear());

describe("lookup of a term the catalogue has never seen", () => {
  it("adds a verified term to the shared catalogue and lists the real papers it found", async () => {
    mockApi([
      [
        /\/lookup$/,
        {
          status: "added",
          stored: true,
          persisted: true,
          query: "long covid",
          label: "Post-Acute COVID-19 Syndrome",
          entity_id: "MESH:D000094024",
          kind: "condition",
          verified_by: "MeSH",
          reason: "It is a condition heading in NLM MeSH.",
          note: "Not evidence.",
          papers: [
            {
              pmid: "9",
              title: "A real paper",
              journal: "J",
              year: "2024",
              doi: "10.1/x",
              url: "https://doi.org/10.1/x",
            },
          ],
          sources_checked: [],
        },
      ],
    ]);
    const onOpen = vi.fn();
    wrap(<LookupPanel term="long covid" onOpen={onOpen} onOpenLocal={vi.fn()} />);
    expect(
      await screen.findByText(/Verified and added to the shared catalogue/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /A real paper/ })).toHaveAttribute(
      "href",
      "https://doi.org/10.1/x",
    );
    await userEvent.click(screen.getByRole("button", { name: /Open Post-Acute/ }));
    expect(onOpen).toHaveBeenCalledWith("MESH:D000094024");
  });

  it("keeps an unverified term on this device only, and never writes it anywhere shared", async () => {
    const calls = mockApi([
      [
        /\/lookup$/,
        {
          status: "not_verified",
          stored: false,
          query: "flight of the buffalo",
          label: null,
          reason: "It is not a MeSH heading.",
          sources_checked: [],
        },
      ],
    ]);
    const onOpenLocal = vi.fn();
    wrap(<LookupPanel term="flight of the buffalo" onOpen={vi.fn()} onOpenLocal={onOpenLocal} />);
    expect(await screen.findByText(/Not verified as a medical term/)).toBeInTheDocument();
    expect(screen.getByText(/not added to the shared catalogue/)).toBeInTheDocument();
    expect(listLocal()).toHaveLength(0); // nothing is saved until the visitor chooses to
    await userEvent.click(screen.getByRole("button", { name: /Keep it on this device only/ }));
    expect(listLocal().map((t) => t.label)).toEqual(["flight of the buffalo"]);
    expect(onOpenLocal).toHaveBeenCalled();
    expect(calls).toHaveLength(1); // one lookup request, no other call
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ query: "flight of the buffalo" });
  });

  it("explains a refusal of identifying text and offers no way to save it", async () => {
    mockApi([
      [
        /\/lookup$/,
        {
          status: "rejected",
          stored: false,
          reason: "That looks like it may contain personal or identifying information.",
        },
      ],
    ]);
    wrap(<LookupPanel term="jane 555-123-4567" onOpen={vi.fn()} onOpenLocal={vi.fn()} />);
    expect(await screen.findByText(/personal or identifying information/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Keep it on this device/ })).toBeNull();
  });

  it("says nothing was decided when the public services are down", async () => {
    mockApi([
      [
        /\/lookup$/,
        {
          status: "unavailable",
          stored: false,
          query: "x",
          label: null,
          reason: "The public vocabulary service could not be reached.",
          sources_checked: [],
        },
      ],
    ]);
    wrap(<LookupPanel term="x syndrome" onOpen={vi.fn()} onOpenLocal={vi.fn()} />);
    expect(await screen.findByText(/Could not decide/)).toBeInTheDocument();
  });

  it("offers to keep the term locally when the API itself cannot be reached", async () => {
    globalThis.fetch = (async () => {
      throw new TypeError("network");
    }) as typeof fetch;
    wrap(<LookupPanel term="x syndrome" onOpen={vi.fn()} onOpenLocal={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText(/The server could not be reached/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /Keep it on this device only/ })).toBeInTheDocument();
  });

  it("warns the visitor what is sent and not to type identifiers", async () => {
    mockApi([[/\/lookup$/, { status: "rejected", stored: false, reason: "r" }]]);
    wrap(<LookupPanel term="t" onOpen={vi.fn()} onOpenLocal={vi.fn()} />);
    expect(screen.getByText(/Only the term you typed is sent/)).toBeInTheDocument();
    await screen.findByText("r");
  });
});
