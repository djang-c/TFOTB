# Audit A: Hackathon delivery compliance (TFOTB)

Audit date: 2026-10-03 (system clock). Repo HEAD at start: clean `main` (e00ab43 in parent repo; this repo has its own git). Read-only audit; the only file written is this one.
Method: ran the test suite, ran the API locally on port 8101 (killed afterwards), curled every route for real and synthetic entities, read the brief, plan, docs, API and (statically) frontend code. No API key was used, no `.env` sourced, no paid call, nothing under `data/` modified.

## 1. Executive verdict: NOT READY (as a submission); conditionally demonstrable locally

What works and I verified by running it:
- 373/373 tests pass (`PYTHONPATH=src .venv/bin/python -m pytest -q`, 31.7 s). This verifies software behaviour, not scientific correctness.
- The API serves real ontology entities (MONDO/HGNC/HPO, 23,791 diseases, 45,187 genes, 19,894 phenotypes via `/api/meta`), a real phenotype-similarity connection list, live ClinicalTrials.gov studies as "assets", real GARD patient groups, a graph mixing ontology edges with 59 stored paper-derived claims, a cited claim whose quote is verbatim in the cached paper text (I checked `CLAIM:PMID-37245481-e7ed59984e` against `data/cache/texts/PMID-37245481.txt`: present), and a scoped "no supported route" gap with a coverage manifest.
- The MuJoCo sim passes/fails as documented (`valid_transfer` pass, `blocked_path` fail, `modeled_collision`).

Why it is not ready against the brief:
1. There is no collaborator step anywhere (Critical). `/collaborators` returns `[]` for every entity, real and synthetic; the frontend never calls it. No investigator, KOL or network-overlap data exists.
2. The headline seed connection (CLN3 <-> NPC) does not appear in the related-diseases list for either disease, contradicting README item 1 and DEMO_SCRIPT 0:08 (High). It appears only in the graph and `/routes`.
3. No deployment exists, and the deploy image as written would ship no paper claims (High).
4. No OpenAI model use anywhere; no OpenAI adapter exists (High for track eligibility).
5. No video, no recorded 1-minute walkthrough, no 10x milestone analysis or measurement (High; required deliverables).
6. Frontend not built or run by me (deps not installed); everything UI-side is UNVERIFIED.

## 2. Requirement matrix

Status: WORKING = I ran it; PARTIAL; MOCKED = serves synthetic/fixture data; MISSING; UNVERIFIED.

### 2a. Submission deliverables
| # | Brief requirement | Evidence | Status |
|---|---|---|---|
| D1 | Working prototype, deployed or easy to run locally | Local: API runs (`uvicorn atlas.api.app:app`, health ok). No deployed URL anywhere (`grep vercel.app/hf.space` finds none outside DEPLOY.md templates; `docs/DEPLOY.md` is a how-to). Frontend UNVERIFIED (no node_modules). Run-from-clone needs `fetch_ontologies.py` (~440 MB) for real data; otherwise synthetic only (README). | PARTIAL (API local WORKING; frontend UNVERIFIED; deployment MISSING) |
| D2 | Repo with README covering architecture and dataset reproduction | README has what/verify/quick start/limits/layout but no architecture section or diagram (architecture only in `docs/implementation/02-architecture.md`, not linked from README). Dataset reproduction: ontologies via `scripts/fetch_ontologies.py` (not run by me; files already present in `data/raw/`, checksum verification UNVERIFIED). The paper-claim store (`data/store/`, git-ignored) cannot be reproduced without a model key and "recorded responses are not committed" (README). | PARTIAL |
| D3 | Team video | Not present. `docs/BACKLOG.md` T14 = TODO. | MISSING |
| D4 | One-minute walkthrough | `docs/DEMO_SCRIPT.md` is a draft "not from a recording"; no video. Several beats do not match the running system (see F2, F4). | MISSING (script exists, partly inaccurate) |
| D5 | One complete journey disease -> connection -> asset -> collaborator -> action | See section 3. Collaborator step absent for all entities. | PARTIAL (fails at collaborator) |
| D6 | Honest "no supported route" with coverage and missing evidence | `GET /entities/MONDO:0002561/gap` returns kind `no_supported_route`, as_of, coverage manifest id, `missing_information`. Verified for 3 real entities. See F9 for a defect (gap says nothing retrieved while stored claims exist). | WORKING (with defect) |
| D7 | 10x milestone, existing timeline vs route, assumptions | Only `docs/PLAN.md:484-490` plan text, which says measure and "if not 10x, state that". No milestone chosen, no baseline, no measurement, nothing in README/UI/demo script. | MISSING |
| D8 | OpenAI models/tools actually used (track prizes) | `grep -i openai`: only docs/env.example/project rules saying "OpenAI adapter at deployment". `src/atlas/llm/` has only the development adapter. Store extractions: `llm:<development model>@extract-v5`, hypotheses `llm:<development model>@hypothesis-v1`. | MISSING |

### 2b. Modules
| # | Requirement | Evidence | Status |
|---|---|---|---|
| M1a | Gene-variant-mechanism (OMIM, ClinVar) | No OMIM or ClinVar ingestion in `src/` (grep). HPO `genes_to_disease` used for gene-disease (gene-level only). One `AFFECTS_TRANSCRIPT` claim in store. Variants: none real; only `SYN:variant-vus-1`. | MISSING for OMIM/ClinVar/variants; gene-disease from HPO WORKING |
| M1b | Disease-phenotype (HPO) | `/connections` real phenotype channel, BMA-Lin over `phenotype.hpoa`, scores e.g. 0.733 (MONDO:0012188). | WORKING |
| M1c | Publication-claim-investigator (PubMed/PMC) | 59 stored claims from 30 ingested papers via Europe PMC/PubMed (ingest log: ingested 30, skipped 9, failed 2). Investigators: none (`/collaborators` empty; no investigator entities in store). | PARTIAL (claims yes, investigators MISSING) |
| M1d | Study-condition-intervention (ClinicalTrials.gov) | `/assets` for MONDO:0018982 returns 21 live-fetched studies (75 fetched, 21 screened); card text cites NCT ids and status. Fetched live at request time with 8 s timeout, 24 h in-memory cache (`src/atlas/trials.py:147,50-59`). | WORKING (network-dependent) |
| M1e | Funding-researcher-asset (NIH RePORTER) | No RePORTER code (`grep RePORTER src`: only mentions in unrelated files, no client). | MISSING |
| M1f | Patient org-disease-registry (NORD, Global Genes, Orphanet, GARD) | GARD listing via `/groups` for MONDO:0008767 (BDSRA Foundation with registry URL) and MONDO:0018982. NORD/Global Genes/Orphanet not used. Labelled "we have not checked these groups". | PARTIAL (GARD only) |
| M1g | Resolve names/synonyms, stable IDs, source/date/confidence per relationship | `/search?q=CLN3` returns gene + disease + synonyms with match tier ("exact synonym", "all words"); resolver tests pass. Claims carry source_url, source_type, retrieved_at (often null in the store; e.g. `retrieved_at: null` in the sample claim). | PARTIAL |
| M2a | Inspect supporting source, distinguish observed vs inferred, surface contradictions | `status` (`reported_observation` / `inference` / `computational_prediction`) on graph edges; `/claims/{id}` returns source_url, verbatim span, extraction method, `contradicting_claims: []` always for real/stored claims (hard-coded `[]` at `routes.py:~366-372`). Contradiction handling exists only in synthetic data (`SYN:disease-d` "conflicting evidence"). | PARTIAL; contradictions MOCKED |
| M2b | Honest gap + coverage | See D6 | WORKING |
| M3a | Mechanistic overlap clustering (variant effect, pathway, phenotype) | No clustering implemented. `grep -i cluster\|louvain\|leiden\|networkx src` finds only comments and a `SEED_CLUSTER` constant (`routes.py:149`). "Cluster" is a hand-picked seed of 4 IDs. Phenotype similarity ranking exists (pairwise). | MISSING (no clustering algorithm or defensibility analysis) |
| M3b | Find what can be shared (registries, natural history, models, biomarkers, trials); duplicates; adaptation | Real: ClinicalTrials.gov studies as `asset_reuse` cards listing "what differs" and "needs expert review". Registries: GARD registry URL. Models/biomarkers/duplicate detection: none. Cards have `entity_id: null` for real assets (see F10). | PARTIAL |
| M3c | Network overlap (shared KOL / investigator / funder) | Not implemented; `/collaborators` is a stub returning `[]` (`routes.py:281-284`). | MISSING |
| UX1 | One global search | `/search` covers disease, gene, phenotype via ontologies; patient group and mechanism are not searchable (GO terms are not returned for "lysosom": only a disease and genes). Frontend UNVERIFIED. | PARTIAL |
| UX2 | Progressive reveal, explain every edge | Edges carry claim_id/predicate/status; claim drawer API works. Similarity edges have `claim_id: None` by design. Frontend UNVERIFIED. | UNVERIFIED (API side WORKING) |
| UX3 | Patient action view | `/actions` returns `evidence_brief` + `asset_reuse` cards with "this_week", `responsible_human`, markdown. No outreach card for real entities (needs a verified contact; none exist). | PARTIAL |

### 2c. Judging criteria
| Criterion | Assessment | Status |
|---|---|---|
| Graph quality | 49 nodes/83 edges for CLN3 (truncated), predicates GENE_ASSOCIATED, ACCUMULATES_IN_COMPARTMENT, SIMILAR_SYMPTOMS, SHARES_PATHOGENIC_PATHWAY_WITH, CANDIDATE_THERAPY_FOR. No clustering, no counterexamples on real data, no validation of similarity ("not validated against any ground truth", README). | PARTIAL |
| Evidence integrity | Strong design: verbatim quote check, ontology-ID resolution, labelled hypotheses (source_type `ai_generated`, `source_url: atlas:ai-hypothesis`, `knowledge_level: prediction`), all `unreviewed`. Weakness: the single CLN3-NPC pathway claim is `context.scope: "background"` (restated known fact, not a new finding); only 1 published + 1 AI-hypothesis pathway claim in the store. | PARTIAL (WORKING mechanically; thin evidence) |
| Patient progress | Real journey reaches studies and patient groups with a registry link, but no collaborator and no sourced proposal to a partner. | PARTIAL |
| 10x impact | Nothing delivered. | MISSING |
| Ambition / product craft | Frontend (Next.js 3D graph, evidence drawer, simulation replay) exists as source (2,078 lines in components/pages) but I could not build or view it. | UNVERIFIED |

## 3. Journey trace

Setup: `cd hackathon/tfotb && PYTHONPATH=src .venv/bin/python -m uvicorn atlas.api.app:app --port 8101` (background; killed after; port 8101 only). `B=localhost:8101/api`. Outputs abbreviated.

### 3a. Real: CLN3 disease (MONDO:0008767)
| Step | Command | Result | Data kind |
|---|---|---|---|
| Search | `curl $B/search?q=CLN3` | HGNC:2074 CLN3 gene; MONDO:0008767 "neuronal ceroid lipofuscinosis 3" (exact synonym); MONDO:0979346/0979347. | REAL (ontologies). Top-level `_synthetic` string says "SYNTHETIC demo dataset..." even for real hits (F8) |
| Entity | `curl $B/entities/MONDO:0008767` | `_synthetic`: "Not synthetic: read from pinned public files". `claims: []` (hard-coded empty for real entities). Template summary from HPO (30 features, CLN3 gene link, 2 subtypes). | REAL; paper claims NOT attached to the entity |
| Connections | `.../connections` | 15 candidates, all "symptom-level lead", e.g. MONDO:0012188 score 0.733. **NPC (MONDO:0018982, 0009757, 0011873) absent.** Same for NPC's list: CLN3 absent (12 results, all symptom-level). | REAL (phenotype channel only; ignores 59 stored paper claims) |
| Related | `.../related` | genes: 1; phenotype_neighbours: 12 | REAL |
| Graph | `.../graph` | 49 nodes, 83 edges, truncated. Includes paper-claim edges: CLN3 -SHARES_PATHOGENIC_PATHWAY_WITH-> NPC (`CLAIM:PMID-37245481-e7ed59984e`, status inference, unreviewed), GO:0005764 lysosome ACCUMULATES edges, NPC CANDIDATE_THERAPY_FOR edges from CHEBI:747211 / CHEBI:50381. | REAL (stored claims) |
| Routes | `.../routes?to=MONDO:0018982` | Paths CLN3 -> GO:0005764 -> NPC with 1 + 4 claim IDs; labels for GO nodes show raw IDs ("GO:0005764"); `reviewed_claims: 0`. | REAL (stored claims) |
| Claim | `$B/claims/CLAIM:PMID-37245481-e7ed59984e` | source_url `https://doi.org/10.1016/j.ebiom.2023.104628`, quote verbatim (verified in cached text), `extraction_method llm:<development model>@extract-v5`, `scope: background`. | REAL |
| Asset | `.../assets` | 2 studies (of 45 fetched): PLX-200 master protocol; "Gene Therapy for Children With CLN3 Batten Disease". Coverage: ClinicalTrials.gov API v2, status ok. | REAL (live fetch) |
| Groups | `.../groups` | GARD list: BDSRA Foundation (family register URL), Beyond Batten, ... | REAL (GARD; unchecked) |
| Collaborator | `.../collaborators` | `{"_synthetic":"SYNTHETIC demo dataset...","items":[]}` | EMPTY (stub) |
| Action | `.../actions` | 3 cards: evidence_brief + 2 asset_reuse. | REAL, template-built |
| Gap | `.../gap` | `gap: null` (candidates exist) | n/a |

### 3b. Real: Niemann-Pick type C (MONDO:0018982)
Entity real (81 HPO features; genes only on subtypes NPC1/NPC2). Connections 12, all symptom-level, mostly NPC subtypes and other NPC-type entries. Assets: 21 ClinicalTrials.gov studies (e.g. NCT00344331 observational, 900 participants, recruiting; NCT05588167). Groups: Ara Parseghian Medical Research Foundation (no registry URL) and others. Collaborators `[]`. Actions: 3 cards. Graph 48 nodes/85 edges incl. paper edges. Gap `null`.

### 3c. Real gap examples
MONDO:0002561 (lysosomal storage disease), MONDO:0001982 (Niemann-Pick disease), MONDO:0019262 (juvenile NCL): `/gap` returns `kind: no_supported_route`, "no candidate connection was retrieved by any channel", `known_claim_ids: []`, coverage manifest ids. The statement is false for MONDO:0019262 (see F9).

### 3d. Synthetic (SYN:*)
- `SYN:disease-a`: 7 claims, 4 connections (reviewed mechanistic lead / symptom-level lead / conflicting evidence / hypothesis only), 2 assets (registry and cell model "for Disease B (synthetic)"), 3 cards (evidence_brief, outreach_note, simulation_report), graph 14/21, collaborators `[]`.
- `SYN:disease-e`: gap `hypothesis_only` with coverage. `SYN:variant-vus-1`: gap `insufficient_coverage`.
- Search for "SYN" returns real gene symbols (FYN, SYNM...) and not the SYN: entities; searching "Disease A" returns real MONDO entries first (a judge cannot find the synthetic example via search; the home page links it).
- `POST /api/actions` and `/api/explain` with a real ID return empty cards/sentences labelled SYNTHETIC; they only work for SYN entities (F10).
- `POST /api/uploads` returns a canned fixture (`quarantined: true`), not an upload handler.
- `POST /api/research`: disabled by default ("On-demand research is turned off on this server").

Conclusion of the trace: real data reaches disease -> related diseases (symptom only) -> studies -> patient groups -> brief. Synthetic demo reaches all steps except collaborator. There is no entity for which the collaborator step returns data.

## 4. Findings

### Critical
**F1. Collaborator step missing entirely.** Brief requires "a collaborator" in the one complete journey and Module 3 network overlap. `routes.py:281-284` returns `items=[]` unconditionally for any entity (verified: MONDO:0008767, MONDO:0018982, SYN:disease-a); the frontend never calls it (`grep collaborators frontend/src` hits only generated types). No investigator extraction or RePORTER ingestion exists.
Repro: `curl localhost:8101/api/entities/MONDO:0008767/collaborators`.
Fix (minimum honest version): extract authors/affiliations from the already-fetched Europe PMC records for the stored claims and trial sponsors/investigators from ClinicalTrials.gov (already fetched); expose shared-person overlap between the CLN3 and NPC records, each with source link; otherwise the UI/README/demo must state "collaborator identification: not implemented" and the demo must not claim a complete journey.

### High
**F2. Seed connection missing from the related-diseases lists; demo beat 0:08 fails.** `connections` for CLN3 lists 15 symptom-level candidates without NPC; NPC's list lacks CLN3. Cause: `search.py:292` passes `self.store.claims` (HPO gene-disease claims built at index time) to `run_query`, not the 59 paper claims in `data/store/atlas.db`. So "literature-supported lead" never appears on real entities and README item 1 / DEMO_SCRIPT 0:08 ("Niemann-Pick type C appears") are not true of the list. The relationship is visible only in the graph and `/routes`.
Repro: `curl $B/entities/MONDO:0008767/connections | python3 -c "import sys,json;print([x['candidate_id'] for x in json.load(sys.stdin)['results']])"`.
Fix: load stored claims into the candidate set for `run_query` (read-only via `claimstore.load_claims`), add a test asserting NPC is a `literature-supported lead` for CLN3 when the seed claim is present.

**F3. No deployment; as-built deploy would drop the paper claims.** No URL in repo. `deploy/api.Dockerfile` copies `src/`, `data/fixtures/`, `CHECKSUMS.json` and fetches ontologies at build time; `data/store/` is git-ignored (`.gitignore`) and not copied, so the deployed API would have zero paper claims, no hypotheses, no CLN3-NPC graph edges. `deploy/hf-space-README.md` says "All data served is SYNTHETIC", which is also wrong for ontology data. Judges would see only symptom-level leads plus live trials. Frontend unverified.
Fix: ship a committed, snapshot of the claim store (`data/store/snapshot/*.jsonl` equivalent; `data/store.before-provenance/` is tracked but is an old pre-provenance copy, not the current one) into the image; deploy, record the URLs in README; test the public URL end to end.

**F4. Video, walkthrough and 10x analysis do not exist.** BACKLOG T14 TODO; DEMO_SCRIPT is a draft "not from a recording"; 10x appears only as a PLAN section with no milestone, baseline or measurement. The brief makes the 10x case one of five judging criteria.
Fix: pick one milestone (PLAN suggests time to a quality-checked collaboration/evidence brief), time a manual baseline and the tool on N tasks, report the ratio even if below 10x; add a short README section. Do not claim 10x without it.

**F5. No OpenAI use.** Track-prize eligibility requires it. Only the development adapter exists; extraction/hypothesis records show the development model. Docs disclose this honestly (project rules, DECISIONS.md:7, risks doc 11) as a "prize-only" risk.
Fix: implement `OpenAIClient` behind `atlas.llm.LLMClient` and re-run extraction for at least the seed paper, recording the model in `extraction_method`; or state in the submission that the track prize is not targeted. Needs owner approval for key/spend.

**F6. No clustering; "defensible clustering" is a judged item.** No community detection or mechanism-based grouping; "cluster" = hand-picked 4-ID seed constant (`routes.py:149`). Similarity score unvalidated (README says so).
Fix: at minimum, cluster the stored-claim + HPO graph by shared GO compartment/pathway and phenotype similarity with a documented method and a counterexample check; or reword so the submission does not claim clustering.

**F7. README lacks architecture; reproduction of the paper-claim dataset is not possible without a key.** Brief requires "architecture and how to reproduce the dataset". README links no architecture doc; recorded model responses are not committed (README, `.gitignore` excludes `data/cache/`, `data/store/`). Judges cannot regenerate the 59 claims.
Fix: add an architecture section (module diagram, data flow) and commit either the claim snapshot or the recorded LLM cache for the seed papers plus a `scripts/ingest_papers.py` replay command that works offline (`LLM_MODE=replay`).

### Medium
**F8. Real responses carry a SYNTHETIC label.** `/search` for CLN3/Niemann returns `_synthetic: "SYNTHETIC demo dataset ..."` at top level although the hits are real ontology records; `/collaborators` likewise. `_wrap` always attaches the demo label (`routes.py:~111-113`). Confusing for a judge and could undermine the evidence-integrity story; per-hit `match`/`source_type` fields are `database_record` and `demo`.
Fix: label per result, not per response, or drop the global label when any real hits are returned.

**F9. Gap statement contradicts stored claims.** MONDO:0019262 ("juvenile neuronal ceroid lipofuscinosis") has the AI hypothesis and GO claims in the store yet `/gap` says "no candidate connection was retrieved by any channel" with `known_claim_ids: []`. Same root cause as F2.
Also: the accepted AI hypothesis links NPC to MONDO:0019262 (a different node from the seed MONDO:0008767; the equivalent CLN3 hypothesis was rejected as "already stored"), so the "AI hypothesis" label in demo beat 0:30 would appear on the NPC <-> juvenile NCL edge, not on the CLN3 edge. Identity fragmentation between MONDO:0008767 and MONDO:0019262 is not explained to users.
Fix: feed stored claims into the gap computation; add a note or xref mapping for the two NCL nodes.

**F10. Several endpoints are fixture-only or return empty for real entities.** `POST /api/actions`, `POST /api/explain` ignore real IDs (empty). Real `asset_reuse` cards have `entity_id: null`. `/entities/{id}` returns `claims: []` for real entities even when stored claims reference them (`routes.py:~234`), so a claim-count view on the entity page cannot show paper evidence; `contradicting_claims` hard-coded `[]` for stored claims.
Fix: return stored claims in the real branch; set card `entity_id`; implement contradiction lookup (`contradicts` field exists in schema).

**F11. Live third-party dependency at request time.** ClinicalTrials.gov and GARD are fetched live with 8 s timeouts; a judge on a restricted or offline network, or an HF Space that cannot reach them, gets "failed" coverage and an empty asset list (UI is designed to say "not the same as no groups", good). The demo's asset step depends on the network.
Fix: commit a dated snapshot for the seed entities and label it with its retrieval date; fall back to it on failure.

**F12. Search misses non-disease entry points.** Brief: disease, gene, symptom, patient group, or mechanism opens the same graph. Patient groups and mechanisms/pathways are not searchable (query "lysosom" returns one disease and unrelated genes with "all words" matches; GO terms are not indexed as results). SYN entities are not discoverable via `/search`.
Fix: index GO terms already loaded and GARD group names for the seed diseases.

### Low
**F13. README overstates "Finds how rare diseases connect ... lists related diseases and says how strong the evidence is" for real data**: every real result I saw is "symptom-level lead" (consistent with the limits section, but item 1's six categories, notably "reviewed mechanistic lead", never occur on real entities; reviewed count is 0 everywhere).
**F14. Labels in graph/routes show raw GO IDs** (route node label "GO:0005764") because GO labels are not resolved by `_label_of`; hurts family readability.
**F15. Dates.** Store/coverage records are stamped 2026-10-04 while the system date here is 2026-10-03 (likely UTC vs local); harmless but worth confirming before quoting "retrieved" dates in a video.
**F16. README test count** "373 tests on 2026-10-04": I observed 373 passed; accurate.
**F17. Doc staleness.** BACKLOG still says T12 demo "on SYNTHETIC data" and T04 "replay only" although real paper ingestion has run (30 ingested, 41 claim rows from HPO g2d among 59 stored claims); DEMO_SCRIPT pre-flight itself notes the frontend build has not been run since origin labels were added.

### Misleading or at-risk text (check before submission)
- README "What it does" 1: implies mechanistic/literature categories are populated on related-diseases lists; on real data only symptom-level appears and NPC is not listed for CLN3 (F2, F13).
- README "What it does" 2: "finds credible papers ... by itself": true in the ingest log (30 ingested), but only runs with a model key and is off in the deployed API.
- DEMO_SCRIPT 0:08 ("Niemann-Pick type C appears" in the related list) is false as built. 0:30 "AI hypothesis label on the pathway claim" attaches to the NPC <-> MONDO:0019262 edge, not CLN3-NPC. 0:42 gap card: real gap exists (MONDO:0002561) but with the F9 inconsistency.
- DEMO_SCRIPT video outline step 1 "Researchers spend most of their time finding and checking connections by hand" is an unsupported assertion (UNVERIFIED; no source).
- `deploy/hf-space-README.md`: "All data served is SYNTHETIC" is inaccurate for ontology data and would mislead judges either way.
- Frontend home banner "Synthetic demo data" depends on `meta.counts_by_source_type.synthetic_fixture > 0`, which is always true because the demo fixture is always loaded (`routes.py:meta`), so the banner appears even on real-data pages' home view; UNVERIFIED visually.
- No claim of 10x or OpenAI use is made in README/UI (good); the absence is the problem, not an overclaim.

## 5. What I could not verify
- Frontend: not built or run (deps not installed); all UI behaviour, accessibility, the evidence drawer, 3D graph, replay page, and the two Playwright specs (`frontend/e2e/`) are UNVERIFIED.
- `scripts/fetch_ontologies.py` reproduction and `data/raw/CHECKSUMS.json` hash match (I did not re-download or re-hash the 440 MB of reference files).
- Live paper ingestion and hypothesis generation (no key used); I only inspected the stored output and ingest log (30 ingested, 9 skipped, 2 failed; one hypothesis run: 1 accepted, rest rejected as "already stored").
- Correctness of biology: BMA-Lin scores, the BMP/lysosome claims and the CLN3-NPC relationship are PREDICTION/unreviewed; I checked only that the quote exists verbatim in the cached text, not that the paper is read correctly or the DOI resolves.
- GARD/ClinicalTrials.gov data accuracy (live fetches returned results; I did not cross-check them against the source sites).
- Docker image build, the GitHub workflow `deploy-api.yml`, Vercel/HF setup, and robotics replay video rendering (`render_replay.py`; not run).
- Whether `make setup`/mise works on a clean machine.
- Licence compliance of HPO commercial use (flagged UNVERIFIED in the repo's own source manifest).

## 6. Commands run (all local, read-only)
- `PYTHONPATH=src .venv/bin/python -m uvicorn atlas.api.app:app --port 8101` (killed; port confirmed free)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider` -> 373 passed
- curl against `/api/{health,meta,search,entities/*,claims/*,research}` and POST `/api/{actions,explain,uploads,research}`
- `robotics/simulate.py fixtures/{blocked_path,valid_transfer}.json --out <scratchpad>` -> fail [modeled_collision] / pass
- SQLite opened `mode=ro` on `data/store/atlas.db`: 59 claims (41 GENE_ASSOCIATED_WITH_DISEASE, 9 ACCUMULATES_IN_COMPARTMENT, 6 CANDIDATE_THERAPY_FOR, 2 SHARES_PATHOGENIC_PATHWAY_WITH of which 1 `ai_generated`, 1 AFFECTS_TRANSCRIPT), 61 quarantined statements.
- `git status` after the audit: only `?? docs/audit/` (untracked; includes this report).
