# 09 — Implementation Phases (2 builders) & Builder-Agent Prompts

Maps PLAN's T01–T24 onto **2 builders over 24h**. PLAN assumes 4 contributors and says to reduce
scope *explicitly* with fewer — the cuts are listed below. Status baseline: `docs/BACKLOG.md`
(T05, T21, T22 DONE; T02, T09, T11, T13, T20, T23 PARTIAL; T01 BLOCKED on science).

## Roles

- **Builder A — Data & Engine:** T01 support, T02 rest, T03, T04, T06–T09, API.
- **Builder B — Experience & Actions:** T12 frontend, T10 actions, T11 UI, T20/T23 robotics binding, T14 packaging.
- **Both:** T01 evidence audit (needs whichever of us can do science review — or disclose none), T13 evaluation.

## Timeline

```
Hour     0    2    4    6    8   10   12   14   16   18   20   22   24
A        [T01 audit ][T02 ][T03 ][T04 extract][T06][T07/T08][T09+API][ T13 ][T14]
B        [T01 audit ][P0 scaffold+fixtures][ T12 explorer (mock) ...][T10][T11 UI][T23][ T13 ][T14 video]
              ▲ T01 gate (H3): cluster chosen or switched       ▲ data freeze (H12)   ▲ feature freeze (H19)
```

**Explicit scope cuts for 2 builders** (PLAN cut order, applied up front): T24 Opentrons adapter,
T19 further omics, T18 clustering, T16 embeddings, T17 ASO/repurposing drafts → all out unless
ahead of schedule. T15 synthetic-case UI → minimal (backend privacy already tested). Graph canvas →
after the evidence drawer works.

**Never cut:** claim provenance, curated DNA/RNA evidence, channel-level explanation, a useful
action card, negative cases, honest gap card, the bounded simulation report/replay.

---

## P0 · Scaffold (B, H3–H5)
```text
Read CLAUDE.md, docs/PLAN.md, docs/implementation/02 and 03. Add without restructuring existing code:
src/atlas/api/ (FastAPI app factory, CORS from env, /api/health, /api/meta stub, stub routers for
every endpoint in doc 03 §4 returning data/fixtures/*.json), .env.example, Makefile (setup, dev, test,
lint, typegen, e2e), frontend/ via create-next-app (latest, TS strict, App Router, Tailwind v4) +
@xyflow/react, elkjs, lucide-react, react-markdown, openapi-typescript, Playwright. Fixtures are
SYNTHETIC-labelled. Existing `pytest -q` and `ruff check .` must still pass. Stop for review.
```

## T02 rest · Entities, coverage, SQLite (A, H3–H5)
```text
Extend src/atlas/schemas.py with Entity, CoverageManifest, GapResult, AssetResult, ActionCard per
docs/implementation/03 §2 (do not change existing models' behaviour). Add SQLite persistence
(src/atlas/db.py) with versioned JSON snapshot export. Tests: valid/invalid fixtures for each model;
round-trip through SQLite; existing tests unchanged.
```

## T03 · ID resolver (A, H5–H7)
```text
Implement src/atlas/resolver.py per docs/implementation/04 + 06 §2: pinned MONDO/HGNC/HPO mapping
files from data/raw (record versions), exact/synonym/xref + rapidfuzz candidates, type filtering,
ambiguity → unresolved with candidates (never merged), variants require assembly + versioned
transcript. Optional LLM pick among ≤8 candidates via dynamic Literal — returns a suggestion only.
Tests: label-built IDs rejected; ambiguous synonym stays unresolved; transcript versions not merged.
```

## T04 · Ingestion + bounded extraction (A, H7–H10)
```text
Only for sources with a completed row in data/manifests/source_manifest.md. Implement
scripts/pipeline steps per docs/implementation/04 and src/atlas/llm/ per 06 §0–1 (provider-agnostic
client, Anthropic adapter with messages.parse + Pydantic, record/replay cache, refusal handling).
Model + prompt + schema pinned in code and listed in DECISIONS.md; get human approval before the
first live call. Quote verification; failures → quarantine with reasons; lineage IDs.
Tests run offline in replay mode.
```

## T06–T08 · Channels (A, H10–H14)
```text
Implement phenotype, dna_variants, rna_effects, molecular_mechanisms, experimental_findings channels
per docs/implementation/05 §1–5 against the EvidenceChannel contract. Missing → availability missing +
score None. Add the tests in 05 §9 and register channels in the API's registry.
```

## T09 + API (A, H14–H17)
Wire registry → `build_result` → coverage manifest; within-category ordering; replace stub routers
with real ones; gap results; collaborators + assets ranked separately. API integration tests for
the PLAN fixture cases.

## T12 · Explorer (B, H5–H14, mock-first)
```text
Implement docs/implementation/08 against NEXT_PUBLIC_MOCK=1: landing, /entity/[id] with the three
question sections, ConnectionCard + ChannelChips, EvidenceDrawer, AssetCard, CollaboratorList,
GapCard, LimitationsPanel, ViewToggle, DatasetBadge; GraphCanvas last. typecheck + lint + build
must pass; screenshots at 1440 and 390 px.
```

## T10 · Action cards (B, H14–H16)
P0 kinds from doc 07 §1 (evidence_brief, outreach_note, asset_reuse, gap_followup); Jinja2
templates; footnotes resolve; denylist test; Markdown export.

## T11 UI (B, H16–H17)
Upload panel over existing `ingest_lab_finding`; contributor confirmation; quarantine reasons shown.

## T20/T23 · Robotics binding (B, H17–H19)
Doc 07 §4: ExperimentProposal → reviewed spec ref → SimulationRun record → API → SimulationReplay
panel. Pre-render replays for deploy.

## T13 · Evaluation (both, H19–H21)
PLAN acceptance table: add the missing ones (assay incompatibility, honest gap, action
traceability) + Playwright demo-path E2E (Journey A, Journey B, simulation report). Reviewer audits
every positive path + counterexample, or the README says no expert review was available.
10× measurement per doc 01 §4.

## T14 · Package (both, H21–H24)
Deploy; README (architecture, dataset reproduction, sources/licence manifest, 10× method + measured
result, limitations); team video + 1-minute walkthrough recorded from the deployed app, cached
output labelled.
