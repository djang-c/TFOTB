import { expect, test, type Page } from "@playwright/test";

// T13 demo-path E2E (docs/implementation/09). Needs the API on :8000. Real-data journeys run only when
// the pinned ontology files are loaded (/api/meta reports `real`); live sources (ClinicalTrials.gov,
// GARD) may be down, so those checks accept the page's honest "could not be checked" state.

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

async function realMode(page: Page): Promise<boolean> {
  const meta = await (await page.request.get(`${API}/meta`)).json();
  return !!meta.real;
}

test.describe("Journey A: a newly diagnosed family searches (real data)", () => {
  test("typo search, pick the disease, see groups and studies with sources", async ({ page }) => {
    test.skip(!(await realMode(page)), "pinned ontology files not loaded");
    await page.goto("/");
    const box = page.getByRole("combobox");
    await box.fill("cln3");
    const option = page.getByRole("option", { name: /^disease neuronal ceroid lipofuscinosis 3/i });
    await expect(option).toBeVisible();
    await option.click();

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("neuronal ceroid lipofuscinosis 3");
    await expect(page.getByText("Written automatically from the records on this page")).toBeVisible();
    // The summary never claims causation from a gene link.
    await expect(page.locator("#summary")).toContainText("a link alone does not show that a gene causes the disease");

    const existing = page.locator("#existing");
    await expect(existing.getByRole("heading", { name: "Patient groups" }).or(existing.getByText("GARD could not be checked"))).toBeVisible();
    await expect(existing.getByText(/not an endorsement/).or(existing.getByText("GARD could not be checked"))).toBeVisible();
  });

  test("a typo still finds the disease, as a suggestion only", async ({ page }) => {
    test.skip(!(await realMode(page)), "pinned ontology files not loaded");
    await page.goto(`/search?q=${encodeURIComponent("tay sacks")}`);
    await expect(page.getByText("No exact match")).toBeVisible();
    await expect(page.getByRole("link", { name: /Tay-Sachs disease/ }).first()).toBeVisible();
  });

  test("a shared abbreviation stays ambiguous", async ({ page }) => {
    test.skip(!(await realMode(page)), "pinned ontology files not loaded");
    await page.goto("/search?q=NPC");
    await expect(page.getByText(/is used by \d+ different entries/)).toBeVisible();
    await expect(page.getByRole("link", { name: /Niemann-Pick disease type C/ }).first()).toBeVisible();
  });
});

test.describe("Journey B: a patient-group leader looks for related work (real data)", () => {
  test("related diseases explain themselves; subtypes are labelled; next steps are drafted", async ({ page }) => {
    test.skip(!(await realMode(page)), "pinned ontology files not loaded");
    await page.goto(`/entity/${encodeURIComponent("MONDO:0018982")}`);
    const shares = page.locator("#shares");
    await expect(shares.getByText(/Symptom overlap/)).toBeVisible();
    await expect(shares.getByText("A more specific form of this disease").first()).toBeVisible();
    // Genes recorded on the subtypes are reported instead of "no gene".
    await expect(page.locator("#summary")).toContainText("genes are recorded on its more specific forms");
    await expect(page.locator("#next").getByText("This week:").first()).toBeVisible();
  });

  test("a sourced gene claim opens with a plain-language explanation", async ({ page }) => {
    test.skip(!(await realMode(page)), "pinned ontology files not loaded");
    await page.goto(`/entity/${encodeURIComponent("MONDO:0008767")}`);
    await page.locator("#summary").getByRole("button", { name: /Citation 1/ }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer.getByText("What this means")).toBeVisible();
    await expect(drawer).toContainText("does not show the gene causes it");
    await expect(drawer.getByText("The source record, verbatim")).toBeVisible();
  });
});

test.describe("Demo walkthrough (synthetic data, always available)", () => {
  test("connections, evidence drawer, action card and simulation", async ({ page }) => {
    await page.goto(`/entity/${encodeURIComponent("SYN:disease-a")}`);
    await expect(page.getByText("Synthetic demo entry.")).toBeVisible();
    await expect(page.locator("#shares li")).toHaveCount(4);
    await page.locator("#summary").getByRole("button", { name: /Citation 1/ }).click();
    await expect(page.getByRole("dialog").getByText("Made-up demo data. Not a real finding.")).toBeVisible();
    await page.getByRole("button", { name: "Close" }).click();
    await page.getByRole("link", { name: "Open simulation" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Can the robot run this plate layout?");
    await expect(page.getByText("A pass never raises confidence in the biology.")).toBeVisible();
  });

  test("an honest gap: the uncertain variant says what is unknown", async ({ page }) => {
    await page.goto(`/entity/${encodeURIComponent("SYN:variant-vus-1")}`);
    await expect(page.locator("#next")).toContainText("What could change this");
  });
});
