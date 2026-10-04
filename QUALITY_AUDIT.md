# Quality audit: TFOTB (The Flight of The Buffalo), 2026-10-04

Scope: the whole repository (`hackathon/tfotb`), audited against the Hack-Nation Challenge 05 brief (`docs/source/challenge-brief.pdf`), `docs/PLAN.md` (including its 2026-10-04 revision) and the owner's end goal. Method: five independent read-only audit agents (delivery, science, security, architecture, product) each ran code and wrote a report (`docs/audit/raw/A-delivery.md`, `B-science.md`, `C-security.md`, `D-architecture.md`, `E-product.md`); their findings were consolidated here, verified findings were fixed with regression tests, and the result was re-run. Companion file: [`REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md).

This report claims no clinical, regulatory, legal or security certification. Standards named by the security agent (OWASP ASVS, OWASP API Security Top 10, CWE) were used as checklists only.

## 1. Executive verdict

| Question | Verdict |
|---|---|
| Is the core Atlas journey demonstrably working? | **Yes, through the API, on real data**: search CLN3 -> Niemann-Pick type C listed as a literature-supported lead in both directions -> cited evidence -> routes -> studies -> patient groups -> researchers -> evidence brief; and a symptoms-only entry point. **Not demonstrated in a browser**: the frontend could not be built (its dependencies are not installed on the audit machine), so every UI behaviour is UNVERIFIED. |
| Is the project ready for submission? | **Not ready.** It is **conditionally ready as a local, labelled demo of the CLN3 / Niemann-Pick seed cluster** once the frontend is built and viewed. |
| Scientific integrity | **Conditionally ready.** No fabricated citation and no clinical directive was found in stored data. An earlier version stored 10% wrong and 15% partly wrong claims; the checks were tightened and the store rebuilt, but the new error rate has **not** been re-sampled. |

**Exact blockers to submission** (all outside what code alone can fix, or needing the owner):
1. Frontend not built, type-checked, linted or viewed since many UI changes (`make lint`, then open the pages).
2. No team video and no recorded one-minute walkthrough (draft script only: `docs/DEMO_SCRIPT.md`).
3. No deployed prototype (files prepared; deployment is an outward action needing the owner's accounts).
4. No measured 10x milestone (baseline, route, assumptions). A judging criterion.
5. No OpenAI model has been run; the adapter exists and is tested against fake HTTP only. Required for the track prizes.
6. Required brief elements still missing: variant-level evidence (OMIM/ClinVar), funders (NIH RePORTER), a validated clustering.

## 2. What was audited and how

| Agent | Focus | Result file |
|---|---|---|
| A | Delivery compliance, journey trace | `docs/audit/raw/A-delivery.md` (verdict: not ready) |
| B | Scientific integrity: 59 stored claims audited against their quotes, negative cases | `B-science.md` (conditionally ready) |
| C | Code correctness, security, privacy leakage, supply chain | `C-security.md` (no Critical; 1 High) |
| D | Architecture, invariants, performance measurements, deployment | `D-architecture.md` (4 High) |
| E | Product scenarios against the running API, accessibility (static) | `E-product.md` (conditionally ready as demo) |

Limits of the agents: all were read-only; none could build the frontend, run the Docker build or the CI workflows, use a model, or check dependency vulnerabilities (no scanner installed). Agent B could verify quotes verbatim for 8 of 59 claims (only one source text was cached then) and used no network, so DOIs were unchecked by it. Agent C's probes made real read-only requests to GARD and ClinicalTrials.gov through the app's own fetchers.

## 3. Findings and what happened to each

Severity by the audit brief: Critical = privacy exposure, unsafe clinical claims, fabricated evidence, or a broken core journey. High = missing core requirement, incorrect scientific relationship, major defect. Medium = robustness, accessibility, maintainability, measured performance. Low = polish.

**Status key:** FIXED (code + regression test + re-run), PARTIAL, OPEN (not fixed; why), DECISION (owner's call).

### Critical / High
| # | Finding (agents) | Status | Evidence |
|---|---|---|---|
| 1 | **No collaborator step**: `/collaborators` returned `[]` for every entity (A, E, D) -- Critical | PARTIAL | `collaborators.py` + route + entity-page block: authors of the papers behind stored claims; ORCID match or "name only (unverified)"; bridges to other diseases (`test_collaborators.py`, 6 tests). Real run: CLN3 -> 13 people, NPC -> 104 people, 26 bridges, e.g. an ORCID-matched author on both a Niemann-Pick type C and a CLN1 paper. Missing: funders/investors, NIH RePORTER, verified contact routes. UI UNVERIFIED. |
| 2 | **Paper claims never reached ranking**; CLN3 and NPC absent from each other's lists; DEMO_SCRIPT beat false (A, D, E) | FIXED | `SearchIndex.set_paper_claims`; run on the rebuilt store: each lists the other as "literature-supported lead" sharing cholesterol in lysosome and late endosome. `tests/test_paper_claims_in_ranking.py` (incl. a real-data test that skips without the reference files). |
| 3 | **A verbatim quote did not have to support the claim**: 6/58 claims wrong (10.3%, Wilson 95% CI 4.8-20.8%), 9 partial, 26% with a defect (B, C-F1) | FIXED (code); error rate after fix NOT re-measured | `_support_problem` in `extraction.py`: the quote must name both entities (for accumulation: the disease and the substance); negated quotes quarantined; animal evidence refused as a human gene-disease association; hedged quotes flagged. 5 tests. Rebuilding the store dropped 59 -> 39 claims; the specific wrong claims B named are absent (grep of the snapshot). Not caught by design: e.g. a sentence about tau/amyloid stored as a MAPT association where the entity names do appear. |
| 4 | **Contradiction handling did not work**: nothing set `contradicting_claim_ids`; `conflicting_evidence` unreachable; direction compared as raw strings (B, D) | FIXED | `normalize.direction_class`, `channels/claims.py`; 4 end-to-end tests through `run_query`. Limit: no real contradiction exists in the stored papers; extraction does not yet capture counter-statements. |
| 5 | **False UI/API statements**: "no other claim from this experiment group", "evidence from papers not extracted yet", hard-coded empty `lineage_siblings`/`contradicting_claims` (B) | FIXED (API); text UNVERIFIED in browser | `/claims/{id}` computes siblings and contradictions from the store (`test_api_store.py`); home-page text rewritten. |
| 6 | **AI hypotheses**: duplicated a paper's own statement; cited an unsupported claim; weak directive filter; could demote a category and count as independent (B, D-F7) | FIXED | `hypotheses.py` (two different papers, no hedged support, stricter directive regex); `ranking.is_evidential` keeps hypotheses out of categories and counts (`test_hypotheses.py`, `test_ranking.py`). The one stored hypothesis was dropped with the store rebuild and is **not regenerated**. |
| 7 | **New channels not additive**: `ranking.py` hard-coded channel names; the extensibility test could not fail (D-F1) | FIXED | `EvidenceChannel.kind`; registry registers mechanism channels; `test_channels.py` now registers an available mechanism channel under a new ID. |
| 8 | **No symptoms-only input** (multi-word symptoms returned nothing); variants, research questions unsupported (D, E) | PARTIAL | `/api/symptoms` + `/symptoms` page: described symptoms -> HPO terms -> candidate diseases + linked genes, labelled hypotheses (`test_phenotype_channel.py`, `test_symptoms_api.py`, real-data test). A logic error was caught and fixed during testing (an absent *child* symptom wrongly implied the *parent* absent). Still MISSING: variant search, free-text research questions, mechanisms and tissues per candidate. |
| 9 | **Research endpoint failed open with no token**; job list and raw errors public; non-ASCII token crashed (C-F5) | FIXED | 503 without a token; token compared as bytes; job list only with the token; errors reduced to the exception type (`test_api_research.py`). |
| 10 | **No deployment; image would ship no paper claims**; CI ran no tests (A, D) | PARTIAL | `scripts/export_deploy_store.py`, `scripts/load_deploy_store.py`, Dockerfile/workflow updated, test+lint gate added. Nothing deployed; `deploy/store/` is git-ignored until the owner reviews and publishes it (DECISION). |
| 11 | **No video / walkthrough / 10x analysis** (A) | OPEN | Not code. Script drafted. |
| 12 | **No OpenAI use** (A) | PARTIAL / DECISION | `llm/openai_client.py` (stdlib), `LLM_PROVIDER`; `test_openai_client.py` (fake HTTP). Live behaviour UNVERIFIED; no model name assumed. |
| 13 | **No clustering** (A) | PARTIAL | `clusters.py` + `/api/clusters`: transparent rule (shared compartment + substance among observed claims), generic hubs skipped, stated limitation. Real result: one cluster, CLN3 + NPC. Not validated; no UI; no variant/pathway clustering. |
| 14 | **README had no architecture section; misleading text** (A) | FIXED | README rewritten (architecture, limits); DEMO_SCRIPT beats corrected; Space README corrected. |

### Medium
| # | Finding | Status | Evidence |
|---|---|---|---|
| 15 | Private-case marker bypassed by lower case, zero-width, non-breaking and full-width variants; upload path and read path unchecked (C-F2, F3) | FIXED | `privacy.py`; `test_privacy_and_urls.py` (8 variants, DB, upload, direct row). It is a tripwire: it cannot recognise real PHI, which must never be entered. |
| 16 | 500 errors from non-string `entity_id` in `/explain`, `/actions` (C-F4) | FIXED | pydantic request models; `/explain` and `/actions` now serve real entities. |
| 17 | Failed ClinicalTrials.gov / GARD fetches cached for 24 h (C-F6, D-F9) | FIXED | 60 s failure TTL; GARD account failures not cached (tests). Live network is still in the request path and the first request per disease takes ~2 s (OPEN). |
| 18 | `/uploads` ignored the body and returned a canned fixture (C-F7, E-H2) | FIXED | bounded model, always `lab_reported` + `unreviewed`, quarantine with reason, in memory, never in public endpoints (`test_api_uploads.py`, 6 tests). |
| 19 | `javascript:`/`data:` source URLs could become links (C-F8) | FIXED backend; UNVERIFIED frontend | `Claim.source_url` validator; `safeHref` helper applied to every external link (not compiled). |
| 20 | Treatment-idea (drug) claims public and unreviewed (C-F9) | DECISION | Shown, labelled hypothesis-only; `hide_drug_claims` switch exists, default off. |
| 21 | Prompt-injection hardening: `</untrusted_data>` not escaped; stored sentences could forge claim rows (C-F10) | FIXED | `wrap_untrusted`, one-line sanitiser (tests). Real adversarial model behaviour UNVERIFIED. |
| 22 | Graph nodes from stored claims lacked `type`; GO IDs shown raw (C-F11, E) | FIXED | `node_type`; labels sidecar `labels.json` written at ingest. |
| 23 | Hop flags ignored predictions and mixed AI+observed hops; routes via generic compartments looked "supported" (B) | FIXED | `graph.py`: a hop needs an observation; routes through a shared compartment are flagged "shared feature, not a mechanism" (`test_graph.py`). |
| 24 | No publication date on claims (B) | FIXED | `published_at` from the paper's record (retrieval date deliberately not stored: it would change daily and make re-ingest look like a conflict). |
| 25 | Unbounded remote reads (C-F12) | FIXED | 25 MB cap in `sources._get` (test). |
| 26 | One bad store row returned HTTP 500 from graph/routes/claims (B) | FIXED | rows that fail validation are skipped. |
| 27 | Real search hits carried a global "SYNTHETIC" banner; `/entities/{id}` returned `claims: []` for real entries (A, E) | FIXED | `_wrap_real` when real hits exist; entry data lists stored claims (real-data test). |
| 28 | `/health` ok while the first search blocks ~10 s (D-F11) | FIXED | `/api/ready` reports index state. The 1.25 GB peak memory is unchanged (OPEN for a free host). |
| 29 | `/actions` rebuilt the claim graph per candidate (1.1 s of 1.9 s) (D-F8) | FIXED | graph built once per brief. Not re-profiled end to end (UNVERIFIED). |
| 30 | Accessibility: 3.78:1 pill contrast, drawer focus not returned, combobox `aria-controls` dangling, stale search responses, `error.tsx` used `retry` (E) | FIXED in source; UNVERIFIED rendered | colour darkened to ~5.8:1 by calculation; focus return, `aria-controls`, stale-response guard, `reset`. |
| 31 | the development model's package missing from the pinned lockfile; a fresh clone cannot run live ingestion (A, D) | DECISION | Edit made then **reverted**: the workspace guard asks a human to approve lockfile changes. Seven lines to add are listed in `docs/DECISIONS.md`. |
| 32 | `data/store.before-provenance/` tracked in git (C) | FIXED | untracked; `.gitignore` covers `data/store.*/`. |

### Open, not fixed (and why)
| # | Finding | Why open |
|---|---|---|
| 33 | **"Independent studies" counts per-side papers** (D-F5): two papers, each about a different disease sharing a GO term, give 2 independent studies for a non-direct link | Semantics need an owner call (is each side's study "independent support" of the pair?). Hypothesis lineages are now excluded. |
| 34 | A preprint and its journal version would count as two studies (B) | Preprints are rejected at ingest; the case cannot arise from the current source filter. UNVERIFIED for other sources. |
| 35 | Free-text tissue/assay compared by string equality (D-F6) | Needs ontology IDs (UBERON) or a normaliser; direction is done. |
| 36 | Variant / transcript / genome-build handling at query time (D-F4) | The resolver validates identity; no channel or search path uses it. Not started. |
| 37 | Approved drugs (miglustat, arimoclomol) display as "hypothesis only" (B) | By design: treatment ideas are never shown as findings. Owner may want a clearer "approved in some regions, not a recommendation" treatment, which needs a sourced regulatory field. |
| 38 | `shared_treatment_inference_allowed` is `true` on symptom-only leads and reads like permission (E) | Naming/UI wording; the brief card only prints the *blocked* case. |
| 39 | `simulate.py` exits 0 when the workflow fails (E) | Intentional for the demo; a `--strict` flag would be a small change. |
| 40 | E2E tests only check copy; real-data tests skip silently without the reference files (E, D) | Needs the frontend installed to improve; CI has no reference data. |
| 41 | Real-data tests and CI: `pytest` in CI runs with no reference files, so the seed-pair test does not run there | Add a cached-data CI job (needs hosting the files). |
| 42 | Patient-organisation search, GO-term search, funder data (A) | Not built. |

## 4. Verification record (commands and results)

All commands from `hackathon/tfotb`. A passing test shows software behaviour, not scientific correctness.

| Check | Command | Result |
|---|---|---|
| Unit + integration tests | `.venv/bin/python -m pytest -q` | **468 passed** (373 before the audit) |
| Lint | `.venv/bin/ruff check .` | all checks passed |
| Simulation | `robotics/simulate.py` on 5 fixtures | `valid_transfer` pass; `blocked_path` fail (modeled_collision); `insufficient_volume` fail (source_volume); `no_tips` fail (tip_availability); `out_of_range` fail (joint_limits) |
| Reference data integrity | `scripts/fetch_ontologies.py` (re-verifies SHA-256 for 7 files against `CHECKSUMS.json`) | no mismatch |
| Seed journey | in-process API check on the rebuilt store | CLN3 <-> NPC both "literature-supported lead"; routes via lysosome and late endosome flagged shared-feature; brief contains "found by AI in https://doi.org..." and a routes section; 4 of 4 CLN3 claims carry a publication date |
| Clusters | `/api/clusters` | one cluster: CLN3 + NPC on cholesterol in lysosome / late endosome |
| Symptoms | `/api/symptoms?q=seizures vision loss ataxia` | neuronal ceroid lipofuscinosis 7, 8, 2 first |
| Collaborators | `/api/entities/MONDO:0018982/collaborators` | 16 papers, 104 people, 26 bridges; ORCID and name-only matches labelled |
| Upload safety | POST with a disguised private marker | quarantined |
| Private-data leak sweep (agent C) | 293 requests over all public routes | 0 hits for `CASE-SYN` (before the privacy fixes; the fixes only tighten it) |
| Secrets in git history (agent C) | 9 key patterns over `git log --all` | 0 hits |
| SQL injection, path traversal, SSRF, XXE (agent C) | probes | not exploitable (constant table names, constant hosts, installed expat limits) |
| **Not run** | frontend build, type-check, lint, Playwright e2e; Docker build; GitHub workflow; dependency vulnerability scan (none installed); `mypy` (not installed; installing needs approval); any live OpenAI call; model behaviour under adversarial input; re-sampling of stored-claim accuracy | UNVERIFIED |

## 5. Scientific limitations the project must disclose
- No expert has reviewed any biological claim; labels are the protection, not review.
- PubMed indexing is a proxy for peer review, not a check of it.
- The AI's reading can be wrong in ways the checks cannot see (sentence exists, names the entities, is not negated, yet is misread). The post-fix error rate is unmeasured.
- The "new finding vs background" label and the "hedged" flag are the model's/regex's judgement. Of the 39 stored paper claims, 37 are labelled background (reviews and restated facts) and 2 are new findings (the seed paper's cholesterol result), so well-known facts show zero independent studies by design. All 39 carry a publication date; 1 is flagged hedged.
- Symptom similarity and symptom-search numbers are shares of recorded annotations, unvalidated, not probabilities. HPO annotations are incomplete and a missing symptom is not evidence of absence.
- Collaborator matches use names as the papers list them ("Chen J"); name-only matches can join different people. Authorship is not endorsement, availability or a contact route.
- Mechanism clusters follow one simple rule over a small evidence base; not validated.
- The evidence base is small: CLN3 disease and Niemann-Pick type C (one seed paper plus 29 others, ~39 claims). No variant-level, RNA or tissue evidence is extracted.
- HPO's commercial licence terms are unresolved; any open-access paper may be read for this hackathon (owner decision), including one under a non-commercial, no-derivatives licence. Revisit before any other use.

## 6. Builder B's responsibilities, checked against the goals

Builder B (Keving) handed his tasks to the project owner. His scope (from `docs/implementation/09-implementation-phases.md`, `docs/DEPLOY.md` and his 49 commits) was checked against the brief and the end goal. **Every item he took on supports a stated goal; none was off-goal.** Several goal-critical pieces fell between the roles and are now the owner's.

| Responsibility | Serves | State after the audit | Now needed from the owner |
|---|---|---|---|
| P0 scaffold (toolchain, Makefile, API, frontend) | runnable prototype (D1) | API works [run]; `make setup` needs `mise`, which is not installed on the audit machine | confirm `make setup` on a clean machine; frontend build |
| T02 rest: entities, coverage, SQLite, snapshot | evidence integrity, reproducibility | works (`test_db.py`, `test_schemas_t02.py`); snapshot checksums verified | none |
| T12 explorer UI (search, entity page Q1-Q3, evidence drawer, 3D graph, simulation page, empty states) | UX principles, journey | UI source reads well (evidence vs hypothesis labelling praised by agent E); **never rendered by any audit** | `make lint`; open pages; fix what is broken; run Playwright |
| API routers (doc 03 table) | journey, honest gaps | now real for search, entity, connections, groups, assets, graph, routes, gap, claims, actions, explain, uploads, collaborators, symptoms, clusters, research; `simulations` serves recorded demo runs by design | keep the `_synthetic` labelling honest when real and demo data mix |
| Real data work he added beyond the plan (HPO gene claims, ClinicalTrials.gov studies, GARD groups, plain-language summaries) | Module 1 (HPO, ClinicalTrials.gov, patient groups), Maria's Q2 | working, network-dependent; failures were being cached 24 h (fixed) | decide whether to ship a dated snapshot of these live sources for a stable demo |
| T20/T23 robotics binding | evidence-linked simulation deliverable | runs, reports, graph-link record exist; the fixtures are generic and have empty `source_claim_ids` | bind one spec to a stored claim, or keep the "generic illustration" label |
| T25 / T27 breadth layer | brief "scale up" | whole HPO/MONDO coverage works for search and symptoms; Orphanet, Reactome, ClinVar not ingested | optional |
| Deploy (HF Space API; Vercel frontend) | submission | files prepared; **not deployed**; image lacked paper claims (fixed in files) | accounts, `HF_TOKEN`, `HF_SPACE`, Vercel project, publish `deploy/store` |
| T13 evaluation journeys (shared) | evidence | 6 Playwright tests check copy only | add tests that open a paper-derived claim and the seed link |
| T14 packaging, video (shared) | submission | script drafted; no video | record it |
| OpenAI adapter (his planning session: "later, for track eligibility") | track prizes | built (offline-tested) after the audit | decide on a real run (spend) |

## 7. Prioritised remaining tasks

Dependencies are in brackets. P0 = needed for a valid submission.

**P0 (owner)**
1. Build and view the frontend: `cd frontend && corepack enable && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm dev`; fix errors; open CLN3, NPC, `/symptoms`, a claim drawer, the collaborator block. [none]
2. Re-sample the stored claims: audit at least 25 of the 39 against their quotes to measure the post-fix error rate (cached texts are in `data/cache/texts`). [none]
3. Choose the 10x milestone and measure it: time N tasks manually vs with the tool; report the ratio even if it is below 10x. [1]
4. Record the one-minute walkthrough and the team video using `docs/DEMO_SCRIPT.md`; correct beats that do not match the screen. [1]
5. Deploy: accounts and tokens, review and publish `deploy/store`, check `/api/ready`, test the public URL. [1, 2]
6. Decide on OpenAI: run extraction of at least the seed paper with an OpenAI model (needs key, `OPENAI_MODEL_*`, a small spend), record the model in the claims, add one live test. [owner's approval]

**P1**
7. Approve pinning the development model's package in the lockfile (seven lines) so a fresh clone can run live ingestion. [none]
8. Read the five papers that were over the size cap and the few that timed out (`ingest_papers.py`; the cap is now 120,000 characters) and regenerate hypotheses (`generate_hypotheses.py`). [spend]
9. Variant evidence: ClinVar/OMIM ingestion, variant resolver wiring, transcript and genome-build mismatch in the claim channels, variant search. [none; large]
10. Funders and investigators: NIH RePORTER client; use ClinicalTrials.gov sponsors and investigators; verified contact routes before any outreach card. [none]
11. Capture contradictions from papers (counter-statements) so the conflicting-evidence path appears on real data. [extraction prompt change; spend]
12. Decide how "independent studies" should count across the two sides of a link (finding 33). [owner]

**P2**
13. Ontology IDs for tissue and assay; direction enum at extraction. 14. Cached-data CI job so real-data tests run in CI. 15. A real e2e suite for the seed journey. 16. Free-text research-question answering grounded in stored claims. 17. Patient-organisation search (GARD/Orphanet/NORD) and GO-term search. 18. A `--strict` exit code for the simulator. 19. Databricks weekly job (bookmarked; needs spend cap). 20. A validated, evaluated clustering (Leiden over a documented projection) only after a leakage-controlled evaluation exists.

## 8. Process notes (things done during this audit that you should know)
- The claim store (`data/store/`) was rebuilt twice from recorded model responses (no model calls) after the extraction checks and claim dates changed; earlier copies are under `data/store.before-*` (git-ignored). The paper claims fell from 59 to 39 as the stricter gate quarantined unsupported ones. The earlier AI hypothesis was dropped and is not regenerated.
- No model call, deployment, push of generated data, or package install was made for the audit. Two live batches of paper reading ran earlier in the session at the owner's request; the dollar cost was not measured.
- A lockfile edit was made and then reverted because the workspace guard asks for a human decision.
- `deploy/store/` was generated locally and is git-ignored on purpose: it holds short quotes from papers (one under a non-commercial, no-derivatives licence) and author names.

## Addendum 2026-10-04 (after the audit): what changed
The audit's open items 1 (frontend), 7 (vendor package pin) and part of 5 (publish `deploy/store`) were acted on by the owner's decisions of 2026-10-04 (`docs/DECISIONS.md`):
- The frontend was replaced by a new design wired to the real API. **Verified (software):** type-check, lint, 47 unit tests, production build, and a headless-Chrome smoke test with 24 checks against the real API (the seed link and its label, evidence drawer with DOI, treatment ideas labelled as hypotheses, symptoms, clusters, simulation, unknown-term lookup both ways, identifier refusal). **Still not verified:** other browsers, phones, accessibility with a screen reader, a deployed URL.
- OpenAI is the only provider; no package or lockfile change is needed.
- `deploy/store/` is committed; author emails were found in affiliation strings and are now stripped.
- New: lookup of unknown terms (`POST /api/lookup`), tested offline (25 tests) and live against NLM MeSH and Europe PMC.
- 10× case added: a `/10x` page next to Simulation (a model with editable assumptions; about 6× on the starting values, so it does not claim 10×). Still not measured.
- Python tests: 499 passing. The audit's other findings (claim error rate not re-sampled, no 10x measurement, no variants or funders, no OpenAI run, no video, no deployment) are unchanged.

## Addendum 2026-10-04 (later): OpenAI runs live
- Open item 5 is closed. The OpenAI adapter has run live: papers are read by GPT-5 mini (`OPENAI_MODEL_FAST`) and hypotheses and experiment reviews use GPT-5 (`OPENAI_MODEL_REASONING`). The latest run read 8 new papers with GPT-5 mini (13 claims kept, 49 proposals quarantined). Claims from the first development runs keep the model that read them in `extraction_method`; `scripts/reread_with_openai.sh` re-reads them with OpenAI but has not been run. The claim checks are unchanged; the error rate has still not been re-sampled.
- Deployment fixes found while checking the free-tier deploy: the API image now ships MuJoCo and the robot scene (the Simulation plan check would otherwise fail on the server), GO and ChEBI (so on-demand research can run there), and an hourly cap on the experiment AI review, which any visitor can trigger.
