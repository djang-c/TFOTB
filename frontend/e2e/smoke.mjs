// Browser smoke test: drives the real frontend against the real API in headless Chrome and checks what a visitor sees.
//   BASE_URL=http://localhost:3000 SHOTS=/tmp/shots node e2e/smoke.mjs
// Needs: the API running, the frontend dev server running, Google Chrome installed (CHROME_PATH overrides the path).
// E2E_LOOKUP_VERIFIED=1 also checks a verified lookup. That ADDS a real term to the API's shared term store
// and needs internet, so point it at a throwaway API (see docs/DEPLOY.md), never at data you care about.
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOTS = process.env.SHOTS ?? "e2e/shots";
const CHROME =
  process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error" && !/WebGL|GPU|swiftshader|Failed to load resource/i.test(m.text()))
    errors.push(`console: ${m.text()}`);
});
const shot = (n) => page.screenshot({ path: `${SHOTS}/${n}.png` });
const text = async (sel) =>
  (await page
    .locator(sel)
    .first()
    .innerText()
    .catch(() => "")) ?? "";

try {
  // 1. Home reads live numbers from the API
  await page.goto(BASE, { waitUntil: "networkidle" });
  check(
    "home: API status shows connected",
    /Connected to the API/.test(await page.locator("[role=status]").first().innerText()),
  );
  check("home: catalogue tile shows a real count", /\d{2},\d{3}/.test(await text("#explore")));
  await shot("01-home");

  // 2. Search for a known disease and open it
  await page.getByRole("combobox").first().fill("CLN3");
  await page
    .getByRole("option")
    .filter({ hasText: /neuronal ceroid lipofuscinosis 3/i })
    .first()
    .waitFor({ timeout: 15000 });
  check("search: live results include CLN3 disease", true);
  await page
    .getByRole("option")
    .filter({ hasText: /neuronal ceroid lipofuscinosis 3/i })
    .first()
    .click();
  await page.waitForURL(/\/entity\/MONDO/);
  await page
    .getByRole("heading", { level: 1 })
    .filter({ hasText: /ceroid/i })
    .waitFor({ timeout: 15000 });
  check("dossier: opens the disease", true);
  check(
    "dossier: is a document, not a second graph (no 3D canvas)",
    (await page.locator("canvas").count()) === 0,
  );
  check(
    "dossier: links to the graph and to clusters",
    (await page.getByRole("link", { name: /Show in graph/ }).count()) === 1 &&
      (await page.getByRole("link", { name: /^Clusters$/ }).count()) >= 1,
  );
  await page.getByText("Related diseases").first().waitFor({ timeout: 20000 });
  check("dossier: lists related diseases", true);
  await shot("02-dossier");

  // 3. The core journey, CLN3 <-> Niemann-Pick type C, with an evidence label
  const npc = page
    .locator("li", { hasText: /Niemann-Pick disease type C/ })
    .filter({ has: page.getByRole("button", { name: /Show route/ }) })
    .first();
  await npc.waitFor({ timeout: 20000 });
  check("connections: Niemann-Pick type C is listed", true);
  check(
    "connections: it carries the literature-supported lead label",
    /literature-supported lead/.test(await npc.innerText()),
  );
  await npc.getByRole("button", { name: /Show route/ }).click();
  await page
    .getByText(/Shared feature, not a causal step/)
    .first()
    .waitFor({ timeout: 15000 });
  check("connections: a route shows 'shared feature, not a causal step'", true);
  await shot("03-connections-route");

  // 4. A claim tab -> evidence drawer: origin label, verbatim passage, DOI link
  const claimBtn = page.getByRole("button", { name: /PMID-/ }).first();
  await claimBtn.waitFor({ timeout: 15000 });
  await claimBtn.click();
  const drawer = page.getByRole("dialog", { name: "Evidence details" });
  await drawer.waitFor();
  await drawer
    .getByText(/Exact source excerpt|reasoning/)
    .first()
    .waitFor();
  const dt = await drawer.innerText();
  check(
    "drawer: says it was found by AI and not reviewed by a human",
    /Found by AI|Treatment idea|AI hypothesis/.test(dt) &&
      /No human has reviewed it|Not reviewed/.test(dt),
  );
  const href = await drawer
    .locator("a[href^='https://doi.org/']")
    .first()
    .getAttribute("href")
    .catch(() => null);
  check("drawer: links the paper's DOI", !!href, href ?? "no DOI link");
  await shot("04-drawer");
  await page.keyboard.press("Escape");
  check("drawer: Escape closes it", (await page.getByRole("dialog").count()) === 0);

  // 5. Treatment ideas on Niemann-Pick type C are shown, labelled as hypotheses, with source and reasoning
  await page.goto(`${BASE}/entity/MONDO:0018982`, { waitUntil: "networkidle" });
  const hyp = page.locator("section", { hasText: "Hypotheses and treatment ideas" }).first();
  await hyp.waitFor({ timeout: 20000 });
  const ht = await hyp.innerText();
  check(
    "treatment ideas: shown and labelled 'hypothesis only, not a recommendation'",
    /Treatment idea: hypothesis only, not a recommendation/.test(ht),
  );
  check(
    "treatment ideas: show the source passage and a DOI link",
    /Source passage:/.test(ht) && (await hyp.locator("a[href^='https://doi.org/']").count()) > 0,
  );
  await shot("05-treatment-ideas");

  // 5b. The graph page: big, one search box, a small panel about the selected node, no route to the dossier
  await page.goto(`${BASE}/explorer?id=MONDO:0008767`, { waitUntil: "networkidle" });
  await page.waitForSelector("canvas", { timeout: 15000 });
  const gbox = await page.locator("canvas").first().boundingBox();
  check(
    "graph: fills the screen",
    !!gbox && gbox.height >= 700 && gbox.width >= 900,
    gbox ? `${Math.round(gbox.width)}x${Math.round(gbox.height)}` : "no canvas",
  );
  check(
    "graph: exactly one search box on the page",
    (await page.getByRole("combobox").count()) === 1,
  );
  check(
    "graph: no way into the dossier from the graph",
    (await page.getByRole("link", { name: /dossier/i }).count()) === 0,
  );
  const nodePanel = page.getByRole("complementary", { name: "Selected node" });
  await nodePanel.getByText("Links in this view").waitFor({ timeout: 15000 });
  check(
    "graph: the panel lists the selected node's links with their sources",
    (await nodePanel.getByRole("button", { name: /Open the evidence/ }).count()) > 0,
  );
  await page.waitForTimeout(2500);
  await shot("05b-graph");

  // 6. Symptoms page: described symptoms, absence, candidates
  await page.goto(`${BASE}/symptoms`, { waitUntil: "networkidle" });
  const sbox = page.getByLabel("Describe symptoms");
  await sbox.fill("seizures, vision loss, ataxia");
  await sbox.press("Enter");
  await page.getByText(/Candidate diseases/).waitFor({ timeout: 25000 });
  check(
    "symptoms: candidates include the neuronal ceroid lipofuscinosis family",
    /neuronal ceroid/i.test(await text("ol")),
  );
  check(
    "symptoms: says they are hypotheses, not diagnoses",
    /not clinical diagnoses/.test(await text("body")),
  );
  await sbox.fill("no hearing loss");
  await sbox.press("Enter");
  await page.getByText("absent:").first().waitFor({ timeout: 25000 });
  check("symptoms: 'no hearing loss' is understood as absent, not as a match", true);
  await shot("06-symptoms");

  // 7. Clusters follow the search: groups around the entry being looked into
  await page.goto(`${BASE}/clusters?id=MONDO:0008767`, { waitUntil: "networkidle" });
  await page.getByText(/Groups around/).waitFor({ timeout: 15000 });
  await page
    .getByText(/Share an observed mechanism: lysosome \(cholesterol\)/)
    .first()
    .waitFor({ timeout: 20000 });
  check("clusters: groups around the searched disease, named by the shared feature", true);
  check(
    "clusters: Niemann-Pick type C is in its mechanism group",
    /Niemann-Pick disease type C/.test(await text("article")),
  );
  await shot("07-clusters");
  const sideGraph = await page
    .getByRole("navigation", { name: "Pages" })
    .getByRole("link", { name: "Graph" })
    .getAttribute("href");
  check(
    "sidebar: the Graph page follows the entry being looked into",
    /id=MONDO(%3A|:)0008767/.test(sideGraph ?? ""),
    sideGraph ?? "",
  );

  // 8. Simulation page: a pass and the intended failure, from the API
  await page.goto(`${BASE}/simulation`, { waitUntil: "networkidle" });
  await page.getByText("Checks passing").waitFor({ timeout: 15000 });
  check("simulation: the valid run passes", true);
  await page.getByRole("button", { name: "blocked_path" }).click();
  await page.getByText(/Run failed \(intended\)/).waitFor({ timeout: 15000 });
  check("simulation: the blocked_path run fails, as intended", true);
  await page.getByRole("button", { name: "Play replay" }).click();
  await shot("07-simulation");

  // 9. A term the catalogue has never seen and that cannot be verified stays on this device only
  await page.goto(BASE, { waitUntil: "networkidle" });
  const search = page.getByRole("combobox").first();
  await search.fill("flight of the buffalo");
  await search.press("Enter");
  const panel = page.getByTestId("lookup-panel");
  await panel.getByText(/Not verified as a medical term/).waitFor({ timeout: 30000 });
  check(
    "unknown term: reported as not verified, nothing added to the shared catalogue",
    /not added to the shared catalogue/i.test(await panel.innerText()),
  );
  await shot("08-lookup-unverified");
  await panel.getByRole("button", { name: /Keep it on this device only/ }).click();
  await page.getByText("on this device only").first().waitFor();
  check(
    "unknown term: saved locally and labelled",
    /not.*in the shared catalogue/i.test(await text("body")),
  );
  await page.reload({ waitUntil: "networkidle" });
  check(
    "unknown term: still there after a reload (kept in this browser)",
    /flight of the buffalo/i.test(await text("h1")),
  );
  await shot("09-local-term");

  // 10. Personal identifiers are refused before anything leaves the browser's own API call
  await page.goto(BASE, { waitUntil: "networkidle" });
  const box2 = page.getByRole("combobox").first();
  await box2.fill("jane doe 555-123-4567");
  await box2.press("Enter");
  await page
    .getByTestId("lookup-panel")
    .getByText(/personal or identifying information/)
    .waitFor({ timeout: 15000 });
  check("identifiers: refused with an explanation", true);

  // 11. Optional: a verified lookup (ibuprofen is a MeSH chemical heading and is not in the pinned disease/gene/symptom files) is added to the shared catalogue with real papers (writes to the API's store)
  if (process.env.E2E_LOOKUP_VERIFIED === "1") {
    await page.goto(BASE, { waitUntil: "networkidle" });
    const b = page.getByRole("combobox").first();
    await b.fill("ibuprofen");
    await b.press("Enter");
    const p = page.getByTestId("lookup-panel");
    await p.getByText(/Verified and added to the shared catalogue/).waitFor({ timeout: 45000 });
    check(
      "verified lookup: added with papers",
      (await p.locator("a[href^='https://']").count()) > 0,
    );
    await p.getByRole("button", { name: /^Open / }).click();
    await page.getByText("Papers that name it").waitFor({ timeout: 15000 });
    check(
      "verified lookup: the new entry shows its papers and a 'not researched yet' gap",
      /not yet researched|No claim about/i.test(await text("body")),
    );
    await shot("10-lookup-added");
  }
} catch (e) {
  check("script finished without an exception", false, String(e).split("\n")[0]);
  await shot("zz-failure").catch(() => {});
}

check("no uncaught browser errors", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
