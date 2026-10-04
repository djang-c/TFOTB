# TFOTB (The Flight of the Buffalo): submission blueprint

Status: draft, checked against the code and the running app on 2026-10-04. All model calls use the OpenAI API. **Before you submit, complete the gate below.**

## Gate: do these before submitting
- [x] **Store packaged.** `deploy/store` holds all 52 claims: 13 read by GPT-5 mini and 39 from the first development runs (shown as `development-model`).
- [ ] **Checks pass on the filming machine.** `make lint`, `make test` and `npm run e2e` (in `frontend/`).
- [ ] **Each beat checked on screen.** If a beat does not match what you see, change the script, not the screen.

---

## 1. Project summary (text submission, 150–300 words; this draft is about 220)

**The problem.** Evidence on rare diseases is scattered across thousands of papers and databases. Finding which diseases are connected, and how well that connection is supported, is slow manual work.

**What we built.** The Flight of the Buffalo (TFOTB) finds open-access, PubMed-indexed papers by itself. GPT-5 mini reads each paper and proposes claims under a strict JSON schema; GPT-5 proposes labelled hypotheses across papers and reviews failed experiment runs. Code keeps a claim only if its quote appears word for word in the paper and its names resolve to real ontology IDs (MONDO, HGNC, HPO). Every claim keeps its quote and DOI link.

**Key features.**
- **Disease dossier:** related diseases, each with its reason (shared gene, mechanism from papers, disease family, similar symptoms) and an evidence label instead of a combined score. AI hypotheses are labelled. Patient groups come from GARD. Export to Markdown or JSON with provenance.
- **3D evidence graph:** click any link to see the exact quote and paper.
- **Clusters:** diseases that share one specific thing with the one you searched.
- **Symptom search:** candidate diseases, shown as research hypotheses, not diagnoses.
- **Closed-loop experiment planner:** the researcher defines parameters, limits, pass criteria and what to change on failure for an overnight robot run. Plans are checked against real pipetting limits and a MuJoCo motion model. The AI only picks among the changes the researcher allowed.

**How we use OpenAI.** Every model call goes through the OpenAI API with strict structured output, and every claim records the model that read it. More credits would let it read the literature for every rare disease instead of one seed cluster, run its paper-finding job weekly, and read each paper twice with two models to catch misreadings.

**Who benefits.** Rare-disease researchers who want leads they can trace to the source.

---

## 2. Demo video (60 s maximum)
Use **CLN3 disease**, not Fabry disease: Fabry disease has no claims from papers in the store, so the evidence drawer would be empty.

| Time | Say | Show | Callout |
|---|---|---|---|
| 0:00–0:08 | "Rare-disease evidence is scattered across thousands of papers. TFOTB puts it in one place, and shows where every link comes from." | Home page. Type "CLN3" and pick *neuronal ceroid lipofuscinosis 3*. | The Flight of the Buffalo |
| 0:08–0:20 | "For a disease, it lists related diseases with the reason for each one: a shared gene, a mechanism reported in papers, the disease hierarchy, or similar symptoms." | Dossier, **Related diseases** (35 rows). Filter by reason, then point at the Niemann-Pick type C row. | Related diseases, each with its reason |
| 0:20–0:30 | "Click any citation for the exact sentence and the paper. It also says who found it: here, an AI read the article, and no human has reviewed it yet." | Click a claim chip. The evidence drawer opens with the verbatim quote, the DOI link, "found by AI" and "unreviewed". | Every claim, traced to its source |
| 0:30–0:40 | "The same evidence as a 3D graph. Every link opens its own evidence." | **Graph** tab. Rotate, click a node, open a link's evidence. | 3D evidence graph |
| 0:40–0:54 | "To test a lead, the researcher defines an overnight experiment: the parameters, limits, pass criteria and what to change on failure. The robot plan is checked against real limits. Each run is scored, and the next run changes only what the researcher allowed." | **Simulation** in the top bar. Show the parameter table and rules, then **Run overnight (synthetic)**, then the overnight log. | Closed-loop experiment: the researcher sets the rules |
| 0:54–1:00 | "Export everything with its sources. Research support only." | Back on the dossier, click **JSON** to download `…-provenance.json`. | Research support only |

Do not say "confidence score", "validated", "peer reviewed", "diagnosis" or "real lab results":
- The overnight run uses SYNTHETIC readings, and the page labels them so.
- Measured results come only from readings the researcher uploads.

---

## 3. Tech video (60 s maximum)

| Time | Say | Show | Callout |
|---|---|---|---|
| 0:00–0:12 | "TFOTB is a FastAPI backend, a SQLite claim store, a React app built on TanStack Start and Vite, and the OpenAI API for reading papers." | Diagram: Europe PMC papers + MONDO/HPO/HGNC files → OpenAI extraction → code checks → SQLite claim store → FastAPI → React app. | FastAPI · SQLite · TanStack Start (React 19) · OpenAI |
| 0:12–0:26 | "The model only proposes. Code decides what becomes a claim: the quote must appear word for word, the relation must be on an allowed list, and both names must resolve to an ontology ID. Anything else goes to quarantine." | `src/atlas/extraction.py` (module docstring), `src/atlas/db.py` (claims and quarantine tables). | The model proposes, code decides |
| 0:26–0:36 | "The graph is drawn with three.js. The searched disease sits in the centre, direct links on the inner shell. Every edge is one stored claim." | `frontend/src/components/KnowledgeGraph.tsx` next to the live graph. | Every edge is one claim |
| 0:36–0:48 | "There's no combined score. Each connection gets an evidence label, and a paper that only restates a known fact is counted separately from independent studies. AI hypotheses must cite at least two stored claims, and they never count as evidence." | `src/atlas/ranking.py` (`independent_support_count`), `src/atlas/hypotheses.py` (docstring). Run `pytest tests/test_hypotheses.py tests/test_ranking.py -q`. | Labels, not scores |
| 0:48–1:00 | "The experiment loop checks robot plans against real liquid-handling limits and a MuJoCo motion model, scores each run with standard assay statistics, and only changes what the researcher's rules allow." | `src/atlas/experiment.py`, `robotics/simulate.py`. Run `pytest tests/test_experiment.py robotics/tests -q`. | Researcher-defined closed loop |

---

## 4. One-page technical report (PDF: `TeamName_OnePager.pdf`)

### The Flight of the Buffalo (TFOTB): traceable evidence for rare-disease research

**1. Challenge.** Connections between rare diseases are spread across papers and databases, and they rarely say how well they are supported. TFOTB turns literature and reference data into links between diseases, genes, symptoms and mechanisms. Every link keeps its source, and it helps plan the experiment that would test a lead.

**2. Tools and models**
- **OpenAI API** (Chat Completions, strict JSON-schema output; one adapter, `src/atlas/llm/openai_client.py`):
  - GPT-5 mini reads each paper's open-access full text and proposes claims with verbatim quotes.
  - GPT-5 proposes hypotheses that must cite stored claims from two different papers, and reviews failed experiment runs, choosing only among the changes the researcher allowed.
  - Every response is cached and every claim names its model, so a rerun replays at no cost.
- **Reference data:** MONDO, HGNC, HPO, GO and ChEBI files, pinned and checked by SHA-256. Papers come from Europe PMC (open access, PubMed-indexed). Patient groups come from GARD.
- **Storage:** a SQLite claim store (`data/store/atlas.db`) with a checksummed snapshot.
- **Backend:** FastAPI and Pydantic. Assay statistics (Z′, CV, 4-parameter logistic fit) use numpy.
- **Frontend:** React 19 on TanStack Start and Vite, with a three.js graph and Tailwind.
- **Robot motion check:** MuJoCo.

**3. What worked**
- **Strict claim checks.** The model proposes; code keeps a claim only if its quote is verbatim, its relation is allowed, and both names resolve to ontology IDs. 52 claims are stored. In the latest GPT-5 mini run, 13 proposals were kept and 49 quarantined.
- **Related diseases from the full reference data.** For CLN3 disease there are 35 related diseases: 3 by shared gene, 1 by mechanism from papers, 1 by a direct paper link, 15 by hierarchy and 25 by symptoms. One disease can have several reasons.
- **Labels instead of a single score.** Independent studies are counted separately from papers that only cite a fact as background, and AI hypotheses are always labelled as hypotheses.
- **A researcher-defined experiment loop.**
  - The plan is checked against real limits.
  - Pass criteria come from published assay guidance: Z′ ≥ 0.5 (Zhang 1999), control CV ≤ 20% (NIH Assay Guidance Manual), and enough points on each flat end of the curve (Sebaugh 2011).
  - The AI can only choose among the changes the researcher allowed.

**4. What was hard, and what comes next**
- **Contradictions.** Opposing effects on a shared feature produce a "conflicting evidence" label naming both claims. No real contradiction has been found in the stored papers yet, so this has only been tested on synthetic claims.
- **Coverage.** Only papers that have been read contribute claims. Many diseases have none yet (Fabry disease, for example), and the app says so instead of implying there is no connection.
- **Lab loop limits.** The overnight demo uses synthetic readings. Liquids, calibration and biology are not simulated. Next: connect to a real plate reader and liquid handler.
- **What more OpenAI credits would unlock.** Today the budget is capped, so only one seed cluster (CLN3 disease and Niemann-Pick type C) has been read in depth. More credits would buy:
  - reading the open-access literature for every watched disease;
  - a weekly reading job (built, switched off because of cost);
  - a second reading of each paper by a second model, keeping only statements both agree on;
  - model-suggested synonyms for unresolved names, and plain-language explanations of graph paths for families;
  - on-demand research for every visitor instead of token holders.
- **Already in the code but not yet shown:** ClinicalTrials.gov matching (`src/atlas/trials.py`), and a neural model that predicts genes and phenotypes from diseases and symptoms.

**5. How the time was spent.** From git: the first commit was on 2026-10-03 at 11:51 PDT and the latest on 2026-10-04 at 00:48 PDT (104 commits in this repository). Work before the first commit is not recorded. The hour-by-hour split is `UNVERIFIED`; fill it in from your own notes, or leave it out.

---

## What was corrected from the earlier draft

| Earlier draft said | What the repository shows |
|---|---|
| Next.js 15 frontend | TanStack Start + React 19 + Vite (`frontend/package.json`). There is no Next.js. |
| "OpenAI-compatible endpoint, with a fallback provider" | All model calls use the OpenAI API; there is no fallback provider. |
| Search "GARD:0006830 – Fabry disease" | Search does not accept GARD IDs (0 results). Fabry disease is GARD 6400, and it has no claims from papers, so the drawer beat would show nothing. Use CLN3 disease. |
| GARD as a source of findings | GARD supplies patient-group listings only (`src/atlas/gard.py`), not claims. |
| Reads clinical trials | `src/atlas/trials.py` exists, but no API route or page uses it. Listed under future work. |
| "Confidence score" in the drawer | No stored claim has a score (0 of 39). The app uses evidence labels and avoids combined scores on purpose. |
| `/search` page, `Graph3D.tsx`, `ActionCardView.tsx`, "View Hypothesis", "Export Spec" | The pages are `/`, `/entity/$id`, `/explorer`, `/clusters`, `/symptoms` and `/simulation`. The files are `KnowledgeGraph.tsx` and `explorer/Cards.tsx`. Exports are dossier Markdown/JSON and Markdown per card. |
| Force-directed 3D graph | A shell layout: the searched node in the centre, direct links on the inner shell (`KnowledgeGraph.tsx`, `layout`). |
| `hypotheses.py` weighs findings by source reliability | `hypotheses.py` makes AI hypotheses that must cite two or more stored claims. Evidence labels and counting independent studies live in `ranking.py`. |
| Robotics simulation is "future expansion" | Built: a researcher-defined closed loop (`src/atlas/experiment.py`, the `/simulation` page) with the MuJoCo motion check. |
| 24-hour build split into hour blocks | Git shows about 13 hours of commits. The split is `UNVERIFIED`. |
| "High-precision extraction" | Precision has not been measured. Replaced with what was measured: 39 kept and 74 quarantined. |
