import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EvidenceDrawerProvider } from "@/components/EvidenceDrawer";
import { useOpenClaim } from "@/lib/drawerContext";
import { claim, mockApi } from "@/test/fixtures";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));

function Opener({ id }: { id: string }) {
  const open = useOpenClaim();
  return <button onClick={() => open(id)}>open</button>;
}
async function show(c: ReturnType<typeof claim>, extra: Record<string, unknown> = {}) {
  mockApi([
    [
      /\/claims\//,
      {
        claim: c,
        subject_label: "Miglustat",
        object_label: "Niemann-Pick disease type C",
        lineage_siblings: [],
        contradicting_claims: [],
        ...extra,
      },
    ],
  ]);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EvidenceDrawerProvider>
        <Opener id={c.claim_id} />
      </EvidenceDrawerProvider>
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "open" }));
  return screen.findByRole("dialog", { name: "Evidence details" });
}

describe("evidence drawer", () => {
  it("labels a drug claim a hypothesis-only treatment idea and still shows the source and DOI", async () => {
    const d = await show(claim());
    expect(d).toHaveTextContent("Treatment idea: hypothesis only, not a recommendation");
    expect(d).toHaveTextContent("Miglustat is a licensed therapy.");
    expect(
      screen.getByRole("link", { name: /Open the article \(DOI 10\.1\/abc\)/ }),
    ).toHaveAttribute("href", "https://doi.org/10.1/abc");
    expect(d).toHaveTextContent("No human has reviewed it.");
  });

  it("shows an AI hypothesis with its reasoning, its model, and the stored claims it was built from", async () => {
    const d = await show(
      claim({
        source_type: "ai_generated",
        predicate: "SHARES_PATHOGENIC_PATHWAY_WITH",
        source_span: "AI hypothesis: both diseases store cholesterol.",
        derived_from: ["CLAIM:a", "CLAIM:b"],
        source_url: "atlas:hypothesis",
      }),
    );
    expect(d).toHaveTextContent("AI hypothesis, not a finding");
    expect(d).toHaveTextContent("(some-model)");
    expect(d).toHaveTextContent("The AI's reasoning (not a quotation from any paper)");
    expect(d).toHaveTextContent("both diseases store cholesterol.");
    expect(d).not.toHaveTextContent("AI hypothesis: both");
    expect(
      screen.getAllByRole("button", { name: "a" }).length +
        screen.getAllByRole("button", { name: "b" }).length,
    ).toBeGreaterThan(1);
    expect(screen.queryByRole("link", { name: /Open the/ })).toBeNull(); // a hypothesis has no article to open
  });

  it("never renders a javascript: source as a link", async () => {
    const d = await show(claim({ source_url: "javascript:alert(1)" }));
    expect(d.querySelectorAll("a[href^='javascript']")).toHaveLength(0);
    expect(d).toHaveTextContent("No web link is recorded for this source.");
  });

  it("says plainly when the source is synthetic demo data", async () => {
    const d = await show(
      claim({
        source_type: "synthetic_fixture",
        predicate: "ASSOCIATED_WITH_PHENOTYPE",
        status: "reported_observation",
        source_url: "https://example.invalid/x",
      }),
    );
    expect(d).toHaveTextContent("Made-up demo data. Not a real finding.");
  });

  it("closes with Escape and returns focus to what opened it", async () => {
    await show(claim());
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "open" })).toHaveFocus();
  });

  it("shows contradictions as both visible", async () => {
    const d = await show(claim({ contradicts: ["CLAIM:z"] }), {
      contradicting_claims: ["CLAIM:z"],
    });
    expect(d).toHaveTextContent("Disagrees with 1 other claim(s)");
    expect(d).toHaveTextContent("Both stay visible");
  });

  it("reports a failed load instead of staying blank", async () => {
    globalThis.fetch = (async () => new Response("{}", { status: 500 })) as typeof fetch;
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <EvidenceDrawerProvider>
          <Opener id="CLAIM:q" />
        </EvidenceDrawerProvider>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "open" }));
    // the drawer retries once before giving up, so allow for the retry delay
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(
      "Could not load CLAIM:q",
    );
  });
});
