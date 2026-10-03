# Decisions
- **Simulator: MuJoCo 3.14.0** (default per PLAN). Open question "existing ROS 2 stack?" unanswered -> no Gazebo. Revisit only if a ROS 2 stack exists.
- **Motion checking is kinematic**: straight-line segments sampled at 1 mm, MuJoCo contact queries + joint-limit tests. No dynamics, no liquids.
- **Failure policy**: first failure stops the run and is reported; nothing is clipped.
- **Environment**: Python 3.12 venv, `requirements.lock` pinned. mp4 replay uses MuJoCo renderer (GLFW on macOS) + imageio-ffmpeg.
- **Scene/spec coupling**: spec coordinates (mm) are authored to match `scene.xml`; the scene hash is recorded per run.
- **LLM provider (2026-10-03, project owner): Anthropic for now; OpenAI at deployment.** PLAN names OpenAI; only Anthropic access exists today and the challenge brief says track prizes need OpenAI models. All services use the provider-agnostic `atlas.llm.LLMClient`; `AnthropicClient` is the current adapter (model IDs from env `LLM_MODEL_REASONING` / `LLM_MODEL_FAST`, defaults `claude-opus-5-5` / `claude-sonnet-5-5`); an `OpenAIClient` adapter is added before deployment. Status: adapter UNVERIFIED (SDK not installed, never run). Before the first live call: install/review the `anthropic` package, pin model + prompt + schema here, get human approval to send data (no PHI/PII; permitted passages only).
- **Volume-ledger tolerance (2026-10-03): `LEDGER_TOL_UL = 1e-9` uL** in `robotics/compile_workflow.py` so valid splits like 0.1 + 0.2 from a 0.3 uL aspirate are not rejected by float round-off (QA finding F1). Real overdraws still fail. Verdicts of the five fixtures are unchanged.
- **Uploads cannot overwrite claims (2026-10-03):** `ingest_lab_finding` quarantines a payload whose `claim_id` already exists (QA finding F2).
- **`fastapi` and `networkx` stay declared though not yet imported:** docs/implementation/02 and 05 plan the API and graph code that will use them.
- **T02 contracts, schema 0.2.0 (2026-10-03, Builder B):**
  - Storage is stdlib `sqlite3` (STRICT tables: indexed columns + validated JSON body) plus a deterministic JSONL snapshot with per-file SHA-256 (`src/atlas/db.py`). No ORM. Postgres is the later path behind the same interface.
  - `GapResult.kind` uses doc 03's enum (`no_supported_route`). PLAN's "supported research route" is a result category, not a gap.
  - Internal ID prefixes: `ORG:` `INV:` `COV:` `CARD:` `RUN:` `SIM:`, and `UNRESOLVED:` for unresolved or ambiguous entities. External prefixes follow Bioregistry spelling.
  - Action-card footnotes are `[^c:<claim_id>]` (doc 07).
  - `Claim` gains optional PLAN provenance fields (`published_at`, `retrieved_at`, `extraction_method`, `source_reported_classification`, `review_notes`, `derived_from`) and the Biolink `knowledge_level` / `agent_type` enums (default `not_provided`). The KGX export is deferred.
  - `mujoco` moved to the `sim` extra so the API image stays slim. `SimulationRun` and `ExperimentProposal` models are still to come (T20/T23).
- **Seed cluster (2026-10-03, project owner): GO on CLN3 disease + Niemann-Pick type C (CLN7 as stretch).** Provisional: made on the agent-drafted audit (`data/manifests/cluster_audit.md`); the headline paper (PMID 37245481) has not yet been read by a human, and no expert reviewer is assigned. All its claims remain `CANDIDATE`/`unreviewed`; nothing may be labelled `reviewed`. Switch cluster if the paper's quotes, the BMP direction or the sample sizes fail a human check, or if no route + counterexample survives.

## 2026-10-03 - No expert reviewer; roles
- Owner is Builder A (evidence engine: T03, T04, T06-T09, T10, T11). Builder B not yet named. Databricks is the platform; which APIs/workspace is still unspecified.
- No domain expert is available. Consequence: all biological claims stay `unreviewed`; README states this plainly. Nothing may be shown as expert-reviewed.
- Builder B is Keving (anonabento). Databricks: about USD 100 credit, reserved for deployment; develop locally first.

## 2026-10-03 - Ontology files downloaded (owner-approved)
- MONDO v2026-09-01, HPO v2026-09-01 (hp.json, phenotype.hpoa, genes_to_disease.txt) and the HGNC complete set were fetched by `scripts/fetch_ontologies.py` into the git-ignored raw-data folder; SHA-256 is recorded in `CHECKSUMS.json` there.
- HPO commercial-use terms remain UNRESOLVED; the owner approved the download for the hackathon demo only.

## 2026-10-03 - T03 resolver rules (deviations from doc 06 draft)
- Fuzzy matches never auto-resolve (doc 06 accepted a single hit at ratio >= 90). Reason: names like "type C1" vs "type C2" score high but are different diseases. Suggestions only; stdlib difflib used instead of rapidfuzz (not installed; no new package).
- A unique label resolves; a synonym or abbreviation resolves only if no other entity uses it at any tier. Found on real MONDO: "NPC" is a synonym of Niemann-Pick type C, nasopharyngeal carcinoma and a susceptibility entry, so it stays ambiguous.
- Real finding for T01: "Juvenile CLN3 Disease" (the paper's disease) matches two MONDO entries (MONDO:0008767 and MONDO:0979346), and MONDO:0019262 is a broader "juvenile NCL" group. The seed fixture needs a human choice of which ID to use; the resolver will not pick.

## 2026-10-03 - Seed ID for CLN3 disease
- Owner decision: use MONDO:0008767 ("neuronal ceroid lipofuscinosis 3") for CLN3 disease in the seed cluster. Niemann-Pick type C = MONDO:0018982. Genes: CLN3 = HGNC:2074, NPC1 = HGNC:7897, NPC2 = HGNC:14537.
- UNREVIEWED by any expert. MONDO:0979346 (also named "juvenile CLN3 disease") was not opened and may be a valid alternative; MONDO:0019262 is a broader juvenile NCL group and is not used.

## 2026-10-03 - New claim predicates (owner approved; shared schema change, tell Builder B)
- Added GENE_ASSOCIATED_WITH_DISEASE (gene -> disease, association only), ACCUMULATES_IN_COMPARTMENT (disease -> GO component), SHARES_PATHOGENIC_PATHWAY_WITH (disease -> disease) and CANDIDATE_THERAPY_FOR (CHEBI -> disease).
- The last two are HYPOTHESIS_ONLY: a Claim must be status `inference` or `computational_prediction`, never `reported_observation`, and they can never support a "reviewed mechanistic lead". Extraction records them as `inference`. "Possible cures" therefore always appear as hypotheses, never findings or recommendations.
- No new strong-causal predicate was added: cause -> effect stays on the existing PERTURBS_MECHANISM / AFFECTS_TRANSCRIPT, which already require an observation. The phrase "the other relationships I asked for" was read as gene/DNA -> disease, phenotype -> disease (existing ASSOCIATED_WITH_PHENOTYPE) and therapy -> disease; owner to correct if more were meant.

## 2026-10-03 - First live extraction (PMID:37245481) and a quote-check change
- Owner approved sending the reference-trimmed text of PMID 37245481 (CC BY-NC-ND 4.0; the NC/ND terms were flagged to the owner, who approved this one-time test; no policy for NC/ND sources is set). Input came from a PDF via pypdf (installed with approval; not in requirements.lock). Model: `claude-sonnet-5-5` (adapter default, not yet pinned). One earlier attempt sent `model=""` (empty `LLM_MODEL_FAST=` in .env) and was rejected by the API with a 400 before any model ran; fixed in `anthropic_client.py` with a regression test.
- Result: 7 statements proposed, 0 claims stored, 7 quarantined. The checks behaved as designed; nothing wrong was stored.
- DEVIATION (extraction.py `_squash`): the verbatim-quote check now ignores ALL whitespace, not only runs of it. Reason: PDF text breaks lines mid-word ("ju-\nvenile", "LE/\nLys") so correct quotes failed on layout alone. Characters must still match exactly (a missing hyphen still fails; tested). Effect: 3 of the 7 quarantines were quote failures and now pass that check. The proper fix for the weekly job is full-text XML, not PDF.
- Remaining 7 quarantines are all name resolution, i.e. vocabulary, and need owner decisions (NOT changed): (1) the model wrote "Niemann-Pick Type C (NPC) disease" / "juvenile CLN3 disease (JNCL)" with an abbreviation in brackets, which matches no MONDO name; (2) "juvenile CLN3 disease" is ambiguous between two MONDO entries; (3) cholesterol has no entity type (resolver covers only disease, gene, phenotype), so "cholesterol accumulates in lysosome" cannot be stored; (4) the model mis-typed "treatments available for NPC disease" as a disease (correctly rejected; there is no drug entity type); (5) the prompt does not state each predicate's subject/object types, so ACCUMULATES_IN_COMPARTMENT came back as cholesterol -> disease, the reverse of the intended disease -> GO component.
- Not verified: extraction quality in general. One paper, one run, zero accepted claims.
