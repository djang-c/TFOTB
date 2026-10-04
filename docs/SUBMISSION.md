# TFOTB (The Flight of the Buffalo): submission blueprint

Team: **Obstinacy**.

Status: remade 2026-10-04, checked against the code and the running app. All model calls use the OpenAI API. **Before you submit, complete the gate below.**

## Gate: do these before submitting
- [x] **Store packaged.** `deploy/store` holds all 52 claims: 13 read by GPT-5 mini and 39 from the first development runs (shown as `development-model`).
- [x] **Checks pass on the build machine (2026-10-04).** 516 backend tests, 65 frontend unit tests and 47 of 47 browser checks pass; `ruff` and `eslint` are clean. Re-run them on the machine you film on.
- [x] **Live app (2026-10-04):** https://tfotb-403661953034.us-central1.run.app. Google Cloud Run free tier, one service for the API and the web app (`docs/DEPLOY.md`), at most 3 instances. All 47 browser checks pass against it. The deployed app has no OpenAI key: the AI features work only when someone runs the repo locally with their own key, and the README says so. The first visit after idle takes a few seconds.
- [x] **One-pager PDF:** `docs/Obstinacy_OnePager.pdf` (team Obstinacy; source `docs/Obstinacy_OnePager.html`, text in section 4).
- [ ] **Each beat checked on screen.** If a beat does not match what you see, change the script, not the screen.
- [ ] **The 10× case is half measured.** The product side is measured on the live app (median 2.5 s for Maria's five calls, 7 of 7 checklist items pass; `docs/measurements/journey.json`). The typical-way side is NOT: nobody has been timed yet. `docs/TIMING_STUDY.md` is a one-hour protocol for 3 to 5 people, and the `/10x` page shows their timings once `frontend/public/measurements/timing-results.json` exists. Until then do not call the 10× a result.

---

## 1. Project summary (text submission, 150–300 words; this draft is under 300)

**The problem.** Evidence on rare diseases is scattered across thousands of papers and databases. A patient group leader like Maria cannot easily tell which diseases share her disease's mechanism, what work exists, or who to approach.

**What we built.** The Flight of the Buffalo (TFOTB) finds open-access, PubMed-indexed papers by itself. GPT-5 mini reads each paper and proposes claims under a strict JSON schema; GPT-5 proposes labelled hypotheses across papers and reviews failed experiment runs. Code keeps a claim only if its quote appears word for word in the paper and its names resolve to real ontology IDs (MONDO, HGNC, HPO). Every claim keeps its quote and DOI link.

**Key features.**
- **Disease dossier:** related diseases, each with its reason (shared gene, mechanism from papers, disease family, similar symptoms) and an evidence label instead of a combined score. Patient groups, matched studies and researchers are listed too. Export with provenance.
- **3D evidence graph, Clusters and symptom search:** every link opens its quote and paper; symptom results are hypotheses, not diagnoses.
- **10× case:** Maria's journey to a sourced proposal, run live, against the typical way for the brief's four people. The typical-way times are stated assumptions, not measurements.
- **Closed-loop experiment planner:** the researcher sets parameters, limits, pass criteria and failure rules for an overnight robot run, checked against pipetting limits and a MuJoCo motion model.

**How we use OpenAI.** Every model call uses the OpenAI API with strict structured output, and every claim records its model. More credits would read the literature for every rare disease instead of one seed cluster, run paper-finding weekly, and read each paper twice with two models.

**Who benefits.** Patient groups and rare-disease researchers who want leads they can trace to the source.

---

## 2. Demo video (60 s maximum)
Use **CLN3 disease**, not Fabry disease: Fabry disease has no claims from papers in the store, so the evidence drawer would be empty.

| Time | Say | Show | Callout |
|---|---|---|---|
| 0:00–0:07 | "Rare-disease evidence is scattered across thousands of papers. TFOTB puts it in one place, and shows where every link comes from." | Home page. Type "CLN3" and pick *neuronal ceroid lipofuscinosis 3*. | The Flight of the Buffalo |
| 0:07–0:18 | "For a disease, it lists related diseases with the reason for each one: a shared gene, a mechanism reported in papers, the disease hierarchy, or similar symptoms." | Dossier, **Related diseases** (35 rows). Filter by reason, then point at the Niemann-Pick type C row. | Related diseases, each with its reason |
| 0:18–0:27 | "Click any citation for the exact sentence and the paper. It says who found it: here, an AI read the article, and no human has reviewed it yet." | Click a claim chip. The drawer shows the verbatim quote, the DOI link, "found by AI" and "unreviewed". Pick a **GPT-5 mini** claim if you show the model name. | Every claim, traced to its source |
| 0:27–0:34 | "The same evidence as a 3D graph. Every link opens its own evidence." | **Graph** tab. Rotate, click a node, open a link's evidence. | 3D evidence graph |
| 0:34–0:48 | "Maria's question is how fast she can get from her disease to a sourced proposal for a partner. Here are her four steps, run live. Typical way, on our stated assumptions, about 30 working days. Here a person only checks sources: about 11 hours. The assumptions are on the page, and none is measured." | **10× case** in the top bar. Click **Run Maria's journey**, then scroll to the Maria card with the 22× figure and the stress test. | 10× case: the assumptions are on the page |
| 0:48–0:56 | "To test a lead, the researcher defines an overnight experiment. The robot plan is checked against real limits, each run is scored, and the next run changes only what the researcher allowed." | **Simulation** in the top bar. **Run overnight (synthetic)**, then the log. | Closed loop: the researcher sets the rules |
| 0:56–1:00 | "Export everything with its sources. Research support only." | Back on the dossier, click **JSON**. | Research support only |

Do not say "confidence score", "validated", "peer reviewed", "diagnosis", "measured 10×" or "real lab results":
- The 10× figures are arithmetic on stated assumptions. The time with TFOTB is a person checking sources.
- The overnight run uses SYNTHETIC readings, and the page labels them so.
- Measured results come only from readings the researcher uploads.

---

## 3. Tech video (60 s maximum): the whole app, end to end
About 150 words at a normal pace. Show screens, not one example: any disease or gene works for the search beats.

| Time | Say | Show |
|---|---|---|
| 0:00–0:10 | "TFOTB brings rare-disease evidence into one place. Papers and public ontologies go in, and a searchable, sourced map of diseases, genes and symptoms comes out." | Home page, the search box. |
| 0:10–0:22 | "GPT-5 mini reads each paper through the OpenAI API and proposes claims. Code checks each one against the paper's text and the ontologies, then stores it with its quote and link." | `src/atlas/extraction.py` docstring, then the `quarantine` table in `src/atlas/db.py` (around line 82). |
| 0:22–0:33 | "A FastAPI backend serves a React app. Search any disease, gene or symptom and get a dossier: related diseases with the reason for each, patient groups, studies and researchers." | Type a search, open the dossier, scroll the related diseases. |
| 0:33–0:42 | "The same evidence opens as a 3D graph and as clusters, and symptom search helps when there is no diagnosis yet." | **Graph** tab, **Clusters** tab, then the **Symptoms** page. |
| 0:42–0:53 | "The 10× case page walks a patient-group leader from disease to a sourced proposal. The simulation tab runs a researcher-defined overnight experiment, checked in MuJoCo." | **10× case** page (click Run), then **Simulation** (Run overnight). |
| 0:53–1:00 | "Everything exports with its sources, live on Google Cloud Run. TFOTB: every connection, traced to its source." | Click **JSON** on a dossier, then the live URL on screen. |

---|---|---|---|
| 0:00–0:12 | "TFOTB is a FastAPI backend, a SQLite claim store, a React app built on TanStack Start and Vite, and the OpenAI API for reading papers." | Diagram: Europe PMC papers + MONDO/HPO/HGNC files → OpenAI extraction → code checks → SQLite claim store → FastAPI → React app. | FastAPI · SQLite · TanStack Start (React 19) · OpenAI |
| 0:12–0:26 | "The model only proposes. Code decides what becomes a claim: the quote must appear word for word, the relation must be on an allowed list, and both names must resolve to an ontology ID. Anything else goes to quarantine." | `src/atlas/extraction.py` (module docstring), `src/atlas/db.py` (claims and quarantine tables). | The model proposes, code decides |
| 0:26–0:36 | "The graph is drawn with three.js. The searched disease sits in the centre, direct links on the inner shell. Every edge is one stored claim." | `frontend/src/components/KnowledgeGraph.tsx` next to the live graph. | Every edge is one claim |
| 0:36–0:48 | "There's no combined score. Each connection gets an evidence label, and a paper that only restates a known fact is counted separately from independent studies. AI hypotheses must cite at least two stored claims, and they never count as evidence." | `src/atlas/ranking.py` (`independent_support_count`), `src/atlas/hypotheses.py` (docstring). Run `pytest tests/test_hypotheses.py tests/test_ranking.py -q`. | Labels, not scores |
| 0:48–1:00 | "The experiment loop checks robot plans against real liquid-handling limits and a MuJoCo motion model, scores each run with standard assay statistics, and only changes what the researcher's rules allow." | `src/atlas/experiment.py`, `robotics/simulate.py`. Run `pytest tests/test_experiment.py robotics/tests -q`. | Researcher-defined closed loop |

---

## 4. One-page technical report (PDF: `Obstinacy_OnePager.pdf`)

### The Flight of the Buffalo (TFOTB): traceable evidence for rare-disease research

**1. Challenge.** Connections between rare diseases are spread across papers and databases, and they rarely say how well they are supported. TFOTB turns literature and reference data into links between diseases, genes, symptoms and mechanisms. Every link keeps its source, and it helps plan the experiment that would test a lead.

**2. Tools and models**
- **OpenAI API** (Chat Completions, strict JSON-schema output; one adapter, `src/atlas/llm/openai_client.py`):
  - GPT-5 mini reads each paper's open-access full text and proposes claims with verbatim quotes.
  - GPT-5 proposes hypotheses that must cite stored claims from two different papers, and reviews failed experiment runs, choosing only among the changes the researcher allowed.
  - Every response is cached and every claim names its model, so a rerun replays at no cost.
- **Reference data:** MONDO, HGNC, HPO, GO and ChEBI files, pinned and checked by SHA-256. Papers come from Europe PMC (open access, PubMed-indexed). Patient groups come from GARD, matched studies from ClinicalTrials.gov.
- **Storage:** a SQLite claim store (`data/store/atlas.db`) with a checksummed snapshot.
- **Backend:** FastAPI and Pydantic. Assay statistics (Z′, CV, 4-parameter logistic fit) use numpy.
- **Frontend:** React 19 on TanStack Start and Vite, with a three.js graph and Tailwind.
- **Robot motion check:** MuJoCo.

**3. What worked**
- **Strict claim checks.** The model proposes; code keeps a claim only if its quote is verbatim, its relation is allowed, and both names resolve to ontology IDs. 52 claims are stored. In the latest GPT-5 mini run, 13 proposals were kept and 49 quarantined.
- **Related diseases from the full reference data.** For CLN3 disease there are 35 related diseases: 3 by shared gene, 1 by mechanism from papers, 1 by a direct paper link, 15 by hierarchy and 25 by symptoms. The mechanism link to Niemann-Pick type C (lysosomal cholesterol) comes from claims in papers about both diseases.
- **Maria's journey runs end to end.** For CLN3 disease the site returns, measured on the live app at a median of 2.5 seconds for all five calls (7 of 7 checklist items pass): related diseases with reasons, 3 patient groups (1 with a registry link), 2 matched studies, 13 researchers from the papers behind the claims (4 matched by ORCID), and a sourced evidence brief.
- **Labels instead of a single score.** Independent studies are counted separately from papers that only cite a fact as background, and AI hypotheses are always labelled as hypotheses.
- **A researcher-defined experiment loop.** The plan is checked against real limits. Pass criteria come from published assay guidance: Z′ ≥ 0.5 (Zhang 1999), control CV ≤ 20% (NIH Assay Guidance Manual), and enough points on each flat end of the curve (Sebaugh 2011). The AI can only choose among the changes the researcher allowed.

**3b. The 10× case (`/10x`).** Milestone, from the brief's "What good looks like": Maria approaches a partner with a sourced proposal for shared research.
- **Typical way** (editable assumptions): who shares our disease characteristics 10 working days; what useful work exists 10; who to approach 5; write the sourced proposal 5. Total 30 working days.
- **With TFOTB:** the same four steps are answered in about 2.5 seconds (measured on the live app, median of 10 runs). What is left is a person checking sources: 3 + 3 + 1 + 4 = 11 working hours. That is about 22×.
- **Stress test:** if checking takes 3× as long, it is about 7×. 10× is lost beyond 2.2×.
- **The other people in the brief:** Devon (3 days to 30 minutes), Priya (the brief's "months per mechanism", taken as 40 days, to 8 hours) and Dr. Osei (10 days to 2 hours). Priya and Dr. Osei are only partly built and the page says so.
- **After the proposal:** a second section models the lab step with the overnight loop: 6× in a lab with its own robot, 12× for a group waiting on a shared one.
- **Measured and not measured.** Measured: the product side (all five calls a median 2.5 s on the live app over 10 runs; a fixed 7-item checklist passes 7 of 7). Not measured: the typical way. To validate: time 3 to 5 real people on the same tasks against one quality rubric (`docs/TIMING_STUDY.md`), run a real plate reader, and measure real turnaround in two or three labs.

**4. What was hard, and what comes next**
- **Contradictions.** Opposing effects on a shared feature produce a "conflicting evidence" label naming both claims. No real contradiction has been found in the stored papers yet, so this has only been tested on synthetic claims.
- **Coverage.** Only papers that have been read contribute claims. Many diseases have none yet (Fabry disease, for example), and the app says so instead of implying there is no connection.
- **Lab loop limits.** The overnight demo uses synthetic readings. Liquids, calibration and biology are not simulated. Next: connect to a real plate reader and liquid handler.
- **What more OpenAI credits would unlock.** Today the budget is capped, so only one seed cluster (CLN3 disease and Niemann-Pick type C) has been read in depth. More credits would buy:
  - reading the open-access literature for every watched disease;
  - a weekly reading job (built, switched off because of cost);
  - a second reading of each paper by a second model, keeping only statements both agree on;
  - model-suggested synonyms for unresolved names, and plain-language explanations of graph paths for families;
  - on-demand research for every visitor instead of token holders;
  - the missing piece of Priya's case: starting from a mechanism and ranking every disease it could reach.
- **Already in the code but not yet shown:** a neural model that predicts genes and phenotypes from diseases and symptoms.

**5. How the time was spent.** From git: the first commit was on 2026-10-03 at 12:01 PDT and the latest on 2026-10-04 at 03:39 PDT (121 commits in this repository). Work before the first commit is not recorded. The hour-by-hour split is `UNVERIFIED`; fill it in from your own notes, or leave it out.

---

## 5. Coverage against the challenge brief

| What judges look for | Where it is | Status |
|---|---|---|
| Graph quality | Evidence graph, Clusters, related diseases with reasons; counterexamples and uncertainty labelled | Built for the seed cluster. Clustering is a stated rule, not validated. |
| Evidence integrity | Verbatim quotes, DOI links, "found by AI", "unreviewed", hypotheses labelled, contradictions surfaced | Built. No expert has reviewed any claim. 39 of 52 claims come from the first development runs, not GPT-5 mini. |
| Patient progress | Maria's journey: related disease, patient groups with registries, studies, researchers, sourced brief | Built end to end for CLN3. Contact route and funders are not built. |
| 10× impact | `/10x`: milestone, typical way against TFOTB for four people, assumptions, stress test, a measured product side, a timing protocol for the people side | Product side measured; typical-way side is assumptions until people are timed. |
| Ambition and product craft | One search, progressive reveal, explain every edge, symptom search, Simulation | Built. Not checked on other browsers or with a screen reader. |
| Built with OpenAI (extract, reconcile, explain) | Extract: GPT-5 mini. Reconcile: ontology resolution in code, synonyms by AI not yet. Explain: briefs and cards are written from stored claims, not by a model. | Extract live. Reconcile and explain are partial. |
| Working prototype | Local run documented. Live deployment pending. | **Open** |
| Repository with README (architecture, reproduce the dataset) | `README.md` | Built |

---

## What was corrected from the earlier draft

| Earlier draft said | What the repository shows |
|---|---|
| Next.js 15 frontend | TanStack Start + React 19 + Vite (`frontend/package.json`). There is no Next.js. |
| "OpenAI-compatible endpoint, with a fallback provider" | All model calls use the OpenAI API; there is no fallback provider. |
| Search "GARD:0006830 – Fabry disease" | Search does not accept GARD IDs (0 results). Fabry disease is GARD 6400, and it has no claims from papers, so the drawer beat would show nothing. Use CLN3 disease. |
| GARD as a source of findings | GARD supplies patient-group listings only (`src/atlas/gard.py`), not claims. |
| Reads clinical trials (no page uses `trials.py`) | Matched ClinicalTrials.gov studies appear in the dossier through `src/atlas/trials.py`. None has been reviewed for eligibility, and the earlier note that no page used it was wrong. |
| "Confidence score" in the drawer | No stored claim has a score. The app uses evidence labels and avoids combined scores on purpose. |
| `/search` page, `Graph3D.tsx`, `ActionCardView.tsx`, "View Hypothesis", "Export Spec" | The pages are `/`, `/entity/$id`, `/explorer`, `/clusters`, `/symptoms`, `/simulation` and `/10x`. The files are `KnowledgeGraph.tsx` and `explorer/Cards.tsx`. Exports are dossier Markdown/JSON and Markdown per card. |
| Force-directed 3D graph | A shell layout: the searched node in the centre, direct links on the inner shell (`KnowledgeGraph.tsx`, `layout`). |
| `hypotheses.py` weighs findings by source reliability | `hypotheses.py` makes AI hypotheses that must cite two or more stored claims. Evidence labels and counting independent studies live in `ranking.py`. |
| Robotics simulation is "future expansion" | Built: a researcher-defined closed loop (`src/atlas/experiment.py`, the `/simulation` page) with the MuJoCo motion check. |
| "10× faster" as a result | A model with stated assumptions (about 22× for Maria on the starting values, about 7× if checking takes 3× as long). Nothing is measured on real people. |
| 24-hour build split into hour blocks | Git shows about 16 hours between the first and latest commit. The split is `UNVERIFIED`. |
| "High-precision extraction" | Precision has not been measured. Replaced with what was measured: 13 kept and 49 quarantined in the latest GPT-5 mini run. |
