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
  // right after an API restart the index is still building; the page says so, then shows connected
  const connected = await page
    .locator("[role=status]", { hasText: "Connected to the API" })
    .first()
    .waitFor({ timeout: 60000 })
    .then(() => true)
    .catch(() => false);
  check("home: API status shows connected", connected);
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
    "dossier: links to the graph",
    (await page.getByRole("link", { name: /Show in graph/ }).count()) === 1,
  );
  const related = page.getByRole("region", { name: "Related diseases" });
  await related.getByRole("group", { name: "Filter by reason" }).waitFor({ timeout: 30000 });
  check("dossier: lists related diseases", true);
  await shot("02-dossier");

  // 3. The core journey, CLN3 <-> Niemann-Pick type C: one row per disease with every reason and its origin
  const npc = related.locator("li", { hasText: /^Niemann-Pick disease type C/ }).first();
  await npc.waitFor({ timeout: 20000 });
  const npcText = await npc.innerText();
  check("related: Niemann-Pick type C is listed", true);
  check(
    "related: it shares a mechanism observed in papers, labelled as from a paper",
    /Same mechanism, observed in papers/.test(npcText) && /from a paper/.test(npcText),
  );
  check(
    "related: the paper's direct link is labelled as a hypothesis",
    /hypothesis in a paper/.test(npcText),
  );
  check(
    "related: reference data is used (shared gene, disease family, similar symptoms)",
    /Same disease family/.test(await related.innerText()) &&
      /Similar symptoms/.test(await related.innerText()),
  );
  check(
    "related: says plainly when no AI hypothesis exists",
    /No AI hypothesis about this disease has been generated yet/.test(await related.innerText()),
  );
  const tall = await page.evaluate(() => document.documentElement.scrollHeight);
  check("dossier: no column makes the page long", tall < 5200, `${tall}px`);
  await shot("03-related");

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

  // 7. The top bar: only Home and Symptoms stand alone; the views of a search appear once something is searched
  const pages = page.getByRole("navigation", { name: "Pages" });
  check(
    "top bar: Home, Symptoms, Simulation and the 10× case",
    (await pages.getByRole("link").allInnerTexts()).join("|") ===
      "Home|Symptoms|Simulation|10× case",
  );
  check(
    "top bar: no views on the standalone pages",
    (await page.getByRole("navigation", { name: "Views of this search" }).count()) === 0,
  );
  check("top bar: no 'seed cluster' anywhere", !/seed cluster/i.test(await text("body")));
  await page.goto(`${BASE}/entity/MONDO:0008767`, { waitUntil: "networkidle" });
  const views = page.getByRole("navigation", { name: "Views of this search" });
  check(
    "after a search: Dossier, Graph and Clusters are offered",
    (await views.getByRole("link").allInnerTexts()).map((t) => t.trim()).join("|") ===
      "Dossier|Graph|Clusters",
  );
  check(
    "after a search: Graph and Clusters follow the searched disease",
    /id=MONDO(%3A|:)0008767/.test(
      (await views.getByRole("link", { name: "Clusters" }).getAttribute("href")) ?? "",
    ),
  );

  // 7b. Clusters: explained, about the searched disease, and closed without a search
  await views.getByRole("link", { name: "Clusters" }).click();
  await page.getByRole("heading", { name: /What is a cluster\?/ }).waitFor({ timeout: 15000 });
  check("clusters: explains what a cluster is", true);
  await page.getByRole("heading", { name: /Linked to the gene CLN3/ }).waitFor({ timeout: 30000 });
  check("clusters: one cluster per shared thing, named after it", true);
  check(
    "clusters: Niemann-Pick type C is in the shared-mechanism cluster",
    /Same mechanism in papers[\s\S]*Niemann-Pick disease type C/.test(await text("main")),
  );
  await shot("07-clusters");
  await page.goto(`${BASE}/clusters`, { waitUntil: "networkidle" });
  check(
    "clusters: without a search it asks for one instead of showing random clusters",
    /Search a disease first/.test(await text("main")),
  );

  // 8. Simulation: the researcher's experiment, the robot plan against real limits, the closed loop
  await page.goto(`${BASE}/10x`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Run Maria/ }).click();
  await page.getByText("Open it on the dossier").first().waitFor({ timeout: 15000 });
  const tenx = await text("main");
  check(
    "10x: Maria's journey runs live, the four people appear, and nothing is claimed as measured",
    /\d+(\.\d)?×/.test(tenx) &&
      /Maria/i.test(tenx) &&
      /Priya/i.test(tenx) &&
      /Dr\. Osei/i.test(tenx) &&
      /No measured speedup/i.test(tenx),
  );
  await shot("07z-10x");
  await page.goto(`${BASE}/simulation`, { waitUntil: "networkidle" });
  await page.evaluate(() => window.localStorage.removeItem("tfotb.experiment.v1"));
  await page.reload({ waitUntil: "networkidle" });
  await page.getByText("Pass criteria (what result you expect)").waitFor({ timeout: 15000 });
  check("simulation: the researcher defines parameters, pass criteria and failure rules", true);
  const steps = page.getByRole("navigation", { name: "Experiment steps" });
  await steps.getByRole("button", { name: /Robot plan/ }).click();
  await page.getByText("The robot can run this plan").waitFor({ timeout: 30000 });
  check(
    "simulation: the plan is checked against pipette, DMSO, stock, tips and robot motion",
    /DMSO limit/.test(await text("main")) && /Robot motion \(MuJoCo\)/.test(await text("main")),
  );
  await shot("08a-simulation-plan");
  // a real constraint: 2 uL of DMSO stock in 100 uL is 2%, over the 1% the example cells tolerate
  await steps.getByRole("button", { name: /Define/ }).click();
  const transfer = page.locator("tr", { hasText: "Compound transfer" }).locator("input").first();
  await transfer.fill("2");
  await steps.getByRole("button", { name: /Robot plan/ }).click();
  await page.getByText("The robot cannot run this plan").waitFor({ timeout: 30000 });
  check(
    "simulation: a plan over the DMSO limit is refused, not adjusted",
    /final DMSO is 2\.00%/.test(await text("main")),
  );
  await steps.getByRole("button", { name: /Define/ }).click();
  await transfer.fill("1");
  await steps.getByRole("button", { name: /Run and evaluate/ }).click();
  await page.getByRole("button", { name: /Run overnight/ }).click();
  await page
    .getByRole("navigation", { name: "Experiment steps" })
    .getByRole("button", { name: /Overnight log \(/ })
    .waitFor({ timeout: 60000 });
  const log = await text("main");
  check(
    "simulation: the overnight loop ends by the researcher's stop rule",
    /Done: confirmed/.test(log),
    log.match(/Done: confirmed[^\n]*/)?.[0] ?? "",
  );
  check("simulation: synthetic readings are labelled", /SYNTHETIC/.test(log));
  check("simulation: the log shows each change the rules made", /Top concentration → /.test(log));
  await shot("08b-simulation-log");
  await steps.getByRole("button", { name: /Run and evaluate/ }).click();
  await page.getByRole("img", { name: "Dose-response curve" }).waitFor({ timeout: 15000 });
  check("simulation: each run is scored against the criteria with a fitted curve", true);
  await shot("08c-simulation-run");

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
