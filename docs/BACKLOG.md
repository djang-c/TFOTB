# Backlog status (from PLAN T01-T24)
Legend: DONE-verified (tests pass), PARTIAL, TODO, BLOCKED (needs human/science). Nothing here is expert-reviewed.

| ID | Status | What exists / what is missing |
|---|---|---|
| T01 Cluster + source audit | PARTIAL - cluster chosen (CLN3 + NPC, owner GO 2026-10-03, provisional); agent draft done, EXPERT REVIEW PENDING | 2026-10-03 AI-read audit: `data/manifests/source_manifest.md` (17 sources; HPO commercial terms, ClinicalTrials.gov, Monarch, PrimeKG UNVERIFIED) and `data/manifests/cluster_audit.md` (19 CANDIDATE / 3 UNVERIFIED rows; cluster re-anchored on CLN3 + NPC). Nothing is `reviewed`; a qualified human must re-check every quote, the BMP direction, the CLN3-CLN7 pairing and registry terms. |
| T02 Schemas | PARTIAL | `src/atlas/schemas.py` (Claim, ChannelComparison, ConnectionResult, validators) + tests. Missing: Entity tables, coverage manifest model, SQLite persistence. |
| T03 ID resolver | PARTIAL | `src/atlas/resolver.py` + `tests/test_resolver.py` (20 tests, offline; real-file tests skip if ontologies are absent). Done: MONDO/HGNC/HPO exact matching in tiers, ambiguity kept with all candidates, fuzzy = suggestions only, label-built IDs rejected, variant assembly + versioned transcript check. Not done: LLM pick among candidates (T04 scope), semantic retrieval, drug/other entity types, not wired into store/API. |
| T04 Ingestion + extraction | PARTIAL (replay only) | `src/atlas/extraction.py` + `tests/test_extraction.py` (11 offline tests, SYNTHETIC text/responses). Model output is only a proposal: quote must appear verbatim in the source, predicate must be allowed, both mentions must resolve via T03, else quarantine with a reason; refusals give `not_extracted`; claims are always `unreviewed`. Provider: Anthropic for now, OpenAI adapter at deployment. NOT done: no live call ever made (no recorded real responses; Anthropic adapter UNVERIFIED, SDK not installed), no source-fetch step, not wired to the store/API. Known gap: the allowed predicate list (splicing-oriented) has no predicate for the seed finding "CLN3 disease and NPC share lysosomal cholesterol storage", so real extraction of the seed paper would quarantine it as NONE_FITS until the owner approves a vocabulary change. |
| T05 Channel contract | DONE-verified | `channels/base.py` registry, candidate union, failure isolation; extension test passes. |
| T06-T08 Channels (phenotype, DNA/RNA/mechanism, assay) | TODO | Contract ready; implementations need curated data. |
| T09 Candidate union + gates | PARTIAL | `ranking.py`: categories, conflict, direction block, lineage count, sim-never-support. Missing: wiring to real channels, coverage manifests. |
| T10 Action cards | TODO | |
| T11 Upload quarantine | PARTIAL | Backend in `store.py` (forced unreviewed, quarantine, inert text, cannot overwrite an existing claim_id). Missing: UI, contributor confirmation, review queue, recompute. |
| T12 Explorer UI | TODO | |
| T13 Evaluation | PARTIAL | Acceptance tests implemented for: missing RNA, mechanism conflict, tissue mismatch, duplicate evidence, upload review, extension, private case, simulation traceability/failure/reproducibility/limits. Not yet: assay incompatibility, honest-gap, action traceability, uncertain-variant n/a (no variant handling exists in code or tests; was wrongly listed as done until the 2026-10-03 QA audit, `reports/qa/2026-10-03-tfotb.md` in the startup-research workspace). |
| T14 Packaging/video | TODO | |
| T15-T19 P1/P2 | TODO | Cut order per PLAN. |
| T20 Contracts frozen | PARTIAL | `experiment_spec.schema.json` + generic fixtures. Not bound to a reviewed research question (blocked on T01/T10). |
| T21 Scene + compiler | DONE-verified (generic) | `scene.xml`, `compile_workflow.py`, `simulate.py` |
| T22 Ledger + failure gates | DONE-verified | Valid passes; insufficient volume, no tips, blocked path, out-of-range fail with reasons. |
| T23 Report/replay/graph link | PARTIAL | JSON/MD report + mp4 replay are generated into `demo_outputs/` (git-ignored). Missing: graph-linked `SimulationRun` record and UI display. |
| T24 Opentrons adapter | TODO (P1) | K-Dense `opentrons-integration` skill available in review clone, not installed. |

Deviation from PLAN: `simulation_time` is recorded as `simulation_steps` + `simulation_time_note` (kinematic samples, not physical time).
