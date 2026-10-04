# Requirements traceability (2026-10-04)

Every requirement from the Hack-Nation Challenge 05 brief (`docs/source/challenge-brief.pdf`, extracted text in `docs/audit/raw/challenge-brief.extracted.txt`) and every capability in the owner's stated end goal, mapped to code, tests and evidence.

**Status words.** WORKING = run and observed to work (by an audit agent or by the author, command named). PARTIAL = part works; the gap is stated. MOCKED = serves synthetic fixture data. MISSING = not built. UNVERIFIED = exists but was not run (the frontend could not be built: its dependencies are not installed on the audit machine).
"Passing tests" shows software behaviour only; it is never offered as proof that the biology is right.

Evidence labels: **[A]** [E] = audit agent reports in `docs/audit/raw/` (A delivery, B science, C security, D architecture, E product); **[run]** = command run by the author after the fixes (see `QUALITY_AUDIT.md` section 4).

## 1. Submission deliverables (brief, "What to Submit")
| # | Requirement | Code / evidence | Status |
|---|---|---|---|
| D1 | Working prototype, deployed or easy to run locally | API: `src/atlas/api`, `make dev`; [run] API answers all journey routes. Frontend: `frontend/` not built (deps absent). No deployed URL. | API WORKING; frontend UNVERIFIED; deployment MISSING (files prepared: `deploy/`, `scripts/export_deploy_store.py`) |
| D2 | Repo with README covering architecture and dataset reproduction | `README.md` (architecture diagram, quick start, limits); `scripts/fetch_ontologies.py` re-verifies SHA-256 for 7 reference files [run]; paper claims need an API key and spend (recorded responses are not committed) | PARTIAL: reference data reproducible; paper layer reproducible only with a key |
| D3 | Team video | none | MISSING |
| D4 | One-minute walkthrough | `docs/DEMO_SCRIPT.md` (draft, not recorded) | MISSING (script only) |
| D5 | One complete journey disease -> connection -> asset -> collaborator -> action | See section 2 | PARTIAL: every step returns real data via the API [run]; collaborator step is author-based and name-matched; UI UNVERIFIED |
| D6 | Honest "no supported route" with coverage and missing evidence | `connections._gap`, `graph.find_paths` gap; tests `test_acceptance.py`, `test_graph.py`; real gap observed for MONDO:0002561 [run] | WORKING |
| D7 | 10x milestone with baseline, route and assumptions | `docs/PLAN.md` section only | MISSING (no milestone chosen, nothing measured) |
| D8 | Actual OpenAI model use (track prizes) | `src/atlas/llm/openai_client.py`, `tests/test_openai_client.py`; live runs with GPT-5 mini (extraction) and GPT-5 (hypotheses, experiment review). Each claim's `extraction_method` names its model: 13 by GPT-5 mini so far; claims from the first development runs keep their own model until `scripts/reread_with_openai.sh` is run. | WORKING (live) |

## 2. The journey, traced (from the API after the fixes) [run]
| Step | Request | Result | Data |
|---|---|---|---|
| Search | `/api/search?q=CLN3` | gene and disease entries with match tier; response labelled "Not synthetic" | real ontologies |
| Related diseases | `/api/entities/MONDO:0008767/connections` | Niemann-Pick type C (MONDO:0018982) listed as **literature-supported lead**; shared `GO:0005764[CHEBI:16113]` (lysosome + cholesterol) and `GO:0005770[CHEBI:16113]` (late endosome); the reverse query lists CLN3 disease | real ontologies + stored paper claims |
| Evidence | `/api/claims/<id>` | verbatim quote, DOI link, "found by AI" extraction method, `unreviewed`, publication date | stored paper claims |
| Routes | `/api/entities/MONDO:0008767/routes?to=MONDO:0018982` | routes through stored claims; routes via a shared compartment are flagged "shared feature, not a mechanism" | stored paper claims |
| Asset | `/api/entities/{id}/assets` | live ClinicalTrials.gov studies with coverage counts | live, network-dependent |
| Patient groups | `/api/entities/{id}/groups` | GARD listing, "not checked or endorsed" | live, network-dependent |
| Collaborator | `/api/entities/{id}/collaborators` | authors of the papers behind the claims, bridges to other diseases, ORCID or "name only (unverified)" | stored paper metadata |
| Action | `/api/entities/{id}/actions` | evidence brief + study-reuse cards citing stored claims; responsible human named | templates over real records |
| No disease named | `/api/symptoms?q=seizures vision loss ataxia` | neuronal ceroid lipofuscinosis family at the top, with linked genes, labelled "research hypothesis, not a diagnosis" | real HPO |

## 3. Brief modules and experience principles
| # | Requirement | Code | Tests | Status |
|---|---|---|---|---|
| M1a | Gene-variant-mechanism (OMIM, ClinVar) | HPO `genes_to_disease` as gene-disease claims (`structured.py`); no OMIM/ClinVar client | `test_structured.py` | PARTIAL: gene level only; variants MISSING |
| M1b | Disease-phenotype (HPO), broad vs informative symptoms | `channels/phenotype.py` (BMA-Lin, IC) | `test_phenotype_channel.py` | WORKING (similarity unvalidated) |
| M1c | Publication-claim-investigator (PubMed/PMC) | `sources.py`, `extraction.py`, `pipeline.py`, `collaborators.py` | `test_extraction.py`, `test_pipeline.py`, `test_collaborators.py` | PARTIAL: claims WORKING; investigators = author lists only |
| M1d | Study-condition-intervention (ClinicalTrials.gov) | `trials.py` | `test_trials.py` | WORKING (live fetch; failures retried after 60 s) |
| M1e | Funding-researcher-asset (NIH RePORTER) | none | none | MISSING |
| M1f | Patient organisation-disease-registry (NORD, Global Genes, Orphanet, GARD) | `gard.py` (GARD only) | `test_gard.py` | PARTIAL |
| M1g | Resolve names/synonyms, stable IDs, source, date, confidence | `resolver.py`, `schemas.Claim` (`published_at` now filled) | `test_resolver.py` | WORKING; no numeric confidence by design |
| M2a | Inspect source; observed vs inferred; contradictions | `Claim.status`, `ranking.py`, `channels/claims.py` | `test_claim_channels.py` (opposing directions -> `conflicting_evidence`) | WORKING on synthetic claims; no real contradiction stored yet |
| M2b | Honest gap with coverage | `connections.py` | `test_acceptance.py` | WORKING |
| M3a | Cluster by variant effect, pathway and phenotype | `clusters.py`, `/api/clusters` | `test_clusters.py` | PARTIAL: rule-based mechanism grouping, not validated, no UI, no variant clustering |
| M3b | Find what can be shared; duplicates; adaptation | `cards.asset_reuse`, ClinicalTrials.gov records | `test_cards.py` | PARTIAL: studies only; models, biomarkers, duplicate detection MISSING |
| M3c | Network overlap (shared investigators) | `collaborators.py` | `test_collaborators.py` | PARTIAL: authors only, name-matched unless ORCID; no funders/investors |
| UX1 | One global search (disease, gene, symptom, group, mechanism) | `search.py`, `/api/symptoms` | `test_search.py`, `test_symptoms_api.py` | PARTIAL: disease, gene, symptom WORKING; patient group and mechanism not searchable |
| UX2 | Progressive reveal; explain every edge | `frontend/src/components/EvidenceDrawer.tsx`; API edges carry `claim_id` | `frontend/e2e` (copy checks only) | API WORKING; UI UNVERIFIED |
| UX3 | Patient action view | `cards.py`, entity page | `test_cards.py` | PARTIAL |

## 4. Judging criteria
| Criterion | Evidence | Status |
|---|---|---|
| Graph quality | claim-edge graph, routes, neighbourhood, mechanism clusters; no counterexamples on real data; similarity unvalidated | PARTIAL |
| Evidence integrity | quote + entity + negation + species checks; origin labels; independent vs background; audit sample found 26% of an earlier store defective, checks tightened, not yet re-sampled | PARTIAL (strong design; empirical error rate after the fix UNVERIFIED) |
| Patient progress | journey reaches studies, patient groups, researchers and a brief | PARTIAL (no sourced partner proposal beyond the brief) |
| 10x impact | none | MISSING |
| Ambition and product craft | UI exists as source; not built or viewed in the audit | UNVERIFIED |

## 5. Owner's end-goal capabilities
| # | Capability | Status | Evidence / gap |
|---|---|---|---|
| 1 | Disease information and research advances | PARTIAL | HPO-based summaries, paper claims, trials; no curated disease descriptions |
| 2 | Papers linked to the studies, experiments, trials they describe | PARTIAL | claims carry DOI + quote; trials listed by condition name; no extraction of a paper's study design or link from paper to a specific registered trial |
| 3 | Possible causes: observed vs association vs prediction vs uncertainty | PARTIAL | `status` (observation / prediction / inference), "association" wording on gene-disease; hedged quotes flagged; scope and review labels |
| 4 | Similarities with exactly what is shared | PARTIAL | symptoms, genes, compartment + substance shown per channel; variants, RNA, pathways, cell types not extracted from papers |
| 5 | Advances for shared features (targeted? in what context?) | PARTIAL | treatment-idea claims (hide switch `hide_drug_claims`), trial lists; no extraction of gene-targeting studies |
| 6 | Honest answers or labelled hypotheses | WORKING | origin labels end to end (`tests/test_cards.py`, `test_api_store.py`); hypotheses cannot change a category (`test_ranking.py`) |
| 7 | No disease named: candidate diseases, genes, features, tissues | PARTIAL | `/api/symptoms`: candidate diseases + genes WORKING [run]; mechanisms and tissues per candidate MISSING; research-question and variant inputs MISSING |

## 6. Negative cases required by the audit brief
| Case | Test or run | Result |
|---|---|---|
| Missing RNA evidence | `test_ranking.py::test_missing_rna_is_missing_not_mismatch_or_confirmation`; live: `rna_effects missing` in the CLN3 comparison [run] | PASS: reported as missing, null score |
| Opposing functional effects in the same gene | `test_claim_channels.py` (4 tests, via `run_query`) | PASS: `conflicting_evidence`, both claims named, shared-treatment inference blocked |
| Ambiguous variant identity | `test_resolver.py` (variant assembly, transcript-version check) | PASS at the resolver; NOT wired into ranking or search (variants MISSING) |
| Repeated publications of one experiment | `test_ranking.py` lineage tests; `test_connections.py` | PASS for same-lineage claims; a preprint and its journal version would count as two (open) |
| Relevant-looking but unsupported citation | `test_extraction.py` gate tests (quote names neither entity; negation; animal evidence); `test_hypotheses.py` (invented or single-paper citations) | PASS |
| Model hypothesis presented as established cause | `test_ranking.py`, `test_cards.py`, `test_api_store.py`, `test_graph.py` | PASS |
| Source/API failure | `test_pipeline.py` (network error, missing recorded response), `test_trials.py`, `test_gard.py`, `test_acceptance.py` | PASS |
| Private case leakage | `test_privacy_and_urls.py` (8 disguised markers), `test_store_privacy.py`; audit C 293-request sweep: 0 hits | PASS (tripwire is defence in depth; real PHI must never be entered) |
| Robotics simulation mistaken for biological validation | `test_simulation.py`, `test_ranking.py`; `robotics/tests` | PASS: `biology` and `physical_execution` forced `not_modeled`; a pass changes no category |

## 7. Plan invariants
| Invariant | Status | Evidence |
|---|---|---|
| Missing is not zero | PASS | ranking, channels, cards |
| No combined score, no LLM confidence | PASS | `grep` of ranking/cards; similarity shown with its definition and "not a probability" |
| IDs never built from labels; unresolved stays unresolved | PASS | `test_resolver.py` |
| One experiment = one lineage | PASS (per paper) | `independent_support_count` |
| Uploads `lab_reported` + `unreviewed`, text inert | PASS | `test_api_uploads.py`, `test_store_privacy.py` |
| Simulation never raises biological confidence | PASS | `test_simulation.py` |
| Coverage counts from recorded operations | PASS | `connections._manifest_id`, `claimstore.paper_coverage` (from the run log) |
| Embeddings retrieve only; clustering is organisation only | PASS trivially: no embeddings exist; clusters carry a stated rule and limitation | `clusters.py` |
| New channel addable without rewriting ranking | PASS | `test_channels.py::test_a_new_available_mechanism_channel_makes_a_lead_without_editing_ranking` |
