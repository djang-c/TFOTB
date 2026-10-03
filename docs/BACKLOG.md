# Backlog status (from PLAN T01-T24)
Legend: DONE-verified (tests pass), PARTIAL, TODO, BLOCKED (needs human/science). Nothing here is expert-reviewed.

| ID | Status | What exists / what is missing |
|---|---|---|
| T01 Cluster + source audit | BLOCKED (science) | Template: `data/manifests/source_manifest.md`. Needs a human/expert to choose the cluster and verify a positive route, counterexample, asset and contact. Not started; nothing fabricated. |
| T02 Schemas | DONE (pending review) | `src/atlas/schemas.py` 0.2.0: Claim, ChannelComparison, ConnectionResult + Entity, CoverageManifest, GapResult, AssetResult, ActionCard with validators; `src/atlas/db.py` SQLite + checksummed snapshot; tests `test_schemas_t02.py`, `test_db.py`. Not yet: SimulationRun/ExperimentProposal (T20/T23), upload fields `sharing_permission`/`result_polarity` (T11), PublicStore on top of AtlasDB. |
| T03 ID resolver | TODO | Only format validation exists (`validate_curie`); no pinned ontology mapping. |
| T04 Ingestion + extraction | TODO | Needs source licence audit (T01) and an approved model/prompt. Provider: Anthropic for now, OpenAI adapter at deployment (DECISIONS.md). `src/atlas/llm/` has the provider-agnostic `LLMClient`, record/replay cache (tested offline) and an UNVERIFIED Anthropic adapter (SDK not installed, never run). No extraction service or live call yet. |
| T05 Channel contract | DONE-verified | `channels/base.py` registry, candidate union, failure isolation; extension test passes. |
| T06-T08 Channels (phenotype, DNA/RNA/mechanism, assay) | TODO | Contract ready; implementations need curated data. |
| T09 Candidate union + gates | PARTIAL | `ranking.py`: categories, conflict, direction block, lineage count, sim-never-support. Missing: wiring to real channels, coverage manifests. |
| T10 Action cards | TODO | |
| T11 Upload quarantine | PARTIAL | Backend in `store.py` (forced unreviewed, quarantine, inert text, cannot overwrite an existing claim_id). Missing: UI, contributor confirmation, review queue, recompute. |
| T12 Explorer UI | PARTIAL (demo on SYNTHETIC data) | Next.js wiki-style explorer: search autocomplete, entity article (Q1-Q3 sections, channel wells, evidence drawer, assets, action cards with .md export, gap card + coverage), 3D graph + list view, `/simulation/[id]` 3D kinematic replay of recorded MuJoCo runs. Data: `scripts/build_demo.py` -> `data/fixtures/demo.json` (SYN: ids). Not yet: Family/Science toggle, upload panel UI, /about, 2D xyflow canvas, e2e tests. |
| T13 Evaluation | PARTIAL | Acceptance tests implemented for: missing RNA, mechanism conflict, tissue mismatch, duplicate evidence, upload review, extension, private case, simulation traceability/failure/reproducibility/limits. Not yet: assay incompatibility, honest-gap, action traceability, uncertain-variant n/a (no variant handling exists in code or tests; was wrongly listed as done until the 2026-10-03 QA audit, `reports/qa/2026-10-03-tfotb.md` in the startup-research workspace). |
| T14 Packaging/video | TODO | |
| T15-T19 P1/P2 | TODO | Cut order per PLAN. |
| T20 Contracts frozen | PARTIAL | `experiment_spec.schema.json` + generic fixtures. Not bound to a reviewed research question (blocked on T01/T10). |
| T21 Scene + compiler | DONE-verified (generic) | `scene.xml`, `compile_workflow.py`, `simulate.py` |
| T22 Ledger + failure gates | DONE-verified | Valid passes; insufficient volume, no tips, blocked path, out-of-range fail with reasons. |
| T23 Report/replay/graph link | PARTIAL | JSON/MD report + mp4 replay are generated into `demo_outputs/` (git-ignored). Missing: graph-linked `SimulationRun` record and UI display. |
| T24 Opentrons adapter | TODO (P1) | K-Dense `opentrons-integration` skill available in review clone, not installed. |

Deviation from PLAN: `simulation_time` is recorded as `simulation_steps` + `simulation_time_note` (kinematic samples, not physical time).
