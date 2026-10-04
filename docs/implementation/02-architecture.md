> **Note 2026-10-04.** The web app is now a TanStack Start single-page app (`frontend/README.md`), not Next.js; the rest of this file is unchanged.

# 02 — Architecture, Stack & Repo Layout

Implements: PLAN "Technical defaults", "Graph schema and identity". Extends the existing
`src/atlas` package instead of introducing a separate `backend/`.

## 1. System overview

```
┌────────────────────────────── frontend/ (Next.js, App Router) ──────────────────────────────┐
│ SearchBar · SummaryCard · RelatedList(channel vectors) · EvidenceDrawer · AssetCard ·        │
│ ActionCard · GapCard · UploadPanel · SimulationReplay · GraphCanvas (optional) · ViewToggle  │
└──────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                           │ JSON; TS types generated from OpenAPI
┌──────────────────────────────────────────▼───────────────────────────────────────────────────┐
│ src/atlas/api/  (FastAPI)  search · entities · connections · claims · assets · gaps ·         │
│                            actions · uploads · simulations · meta                             │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ src/atlas/  schemas · store (public claims + quarantine; isolated CaseStore) · ranking gates  │
│             channels/ (registry + phenotype, dna_variants, rna_effects, molecular_mechanisms, │
│             experimental_findings) · resolver · graph (NetworkX projection) · coverage ·      │
│             llm/ (provider-agnostic client; Anthropic adapter) · actions · explain            │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ robotics/   ExperimentSpec → compile_workflow → simulate (MuJoCo) → report/replay            │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ persistent source of truth: SQLite (claims, sources, coverage manifests) + versioned JSON
        │ built offline by scripts/pipeline/ from cached raw pulls + curated, cited overlays
```

Principles:
- **Read path is offline**: claims, IDs, IC tables, and precomputed channel comparisons are built
  ahead of time; runtime does lookup, gating, and cached explanation.
- **SQLite + versioned JSON is the source of truth; NetworkX is a query projection** (PLAN).
- **Every LLM call goes through `atlas.llm.client`** with record/replay cache; replayed output is
  labelled as cached in the UI (PLAN: "label cached/replayed output accurately").
- **One schema, two languages**: Pydantic in `src/atlas/schemas.py` is the source of truth; frontend
  types are generated from FastAPI's OpenAPI (`openapi-typescript`).

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 venv + `requirements.lock` (existing) | Keep the team's venv convention |
| API | FastAPI, Uvicorn, Pydantic v2 | Add `uvicorn` + `pydantic-settings` to deps |
| Store | SQLite (stdlib `sqlite3`) + JSON snapshots | T02 remaining work |
| Graph | NetworkX `MultiDiGraph` projection | Leiden (`igraph`+`leidenalg`) only if T18 happens |
| Ontology | `pronto` or `obonet` for HPO/MONDO in the pipeline | IC from a pinned, broad annotation corpus |
| LLM | `anthropic` SDK via `atlas.llm` — `client.messages.parse(..., output_format=Model)` | **Proposed: Claude now, OpenAI adapter later** — needs teammate sign-off (doc 11) |
| Robotics | MuJoCo 3.14.0 (existing, DECISIONS.md) | Opentrons adapter = T24, P1 |
| Web | Next.js (latest), React, TypeScript strict, Tailwind v4, `@xyflow/react` + `elkjs` (optional canvas), `lucide-react`, `react-markdown` | PLAN: canvas is optional; evidence drawer is P0 |
| Tests | pytest (existing), Playwright for demo-path E2E | |
| Tooling | ruff (existing), Node 22 + pnpm | |

## 3. Repo layout (additions marked +)

```
TFOTB/
├── CLAUDE.md · README.md · pyproject.toml · requirements.lock
├── docs/
│   ├── PLAN.md                 # authoritative spec
│   ├── BACKLOG.md · DECISIONS.md
│   ├── implementation/        +# these docs: build-level detail per T-task
│   └── source/                +# challenge brief PDF
├── src/atlas/
│   ├── schemas.py · store.py · ranking.py · channels/
│   ├── resolver.py            +# T03
│   ├── coverage.py            +# coverage manifests from recorded operations
│   ├── graph.py               +# NetworkX projection + neighborhood/paths
│   ├── channels/phenotype.py  +# T06 … and the other channel impls (T07, T08)
│   ├── llm/                   +# client.py (interface, cache), anthropic_adapter.py
│   ├── explain.py · actions.py +
│   └── api/                   +# FastAPI app + routers
├── scripts/pipeline/          +# reproducible data build (doc 04)
├── data/
│   ├── manifests/source_manifest.md   # existing licence/access audit (T01)
│   ├── curated/               +# cited YAML overlays (orgs, assets, contacts, reviewed claims)
│   ├── raw/ (gitignored) · build/ · fixtures/ · llm_cache/ +
├── robotics/                  # existing
├── frontend/                  +# Next.js app
└── tests/ · robotics/tests/   # existing
```

## 4. Configuration (`.env.example`, +)

```
LLM_PROVIDER=anthropic                  # anthropic | openai (adapter later)
ANTHROPIC_API_KEY=
LLM_MODEL_REASONING=claude-opus-5-5     # grounded explanation, action-card prose
LLM_MODEL_FAST=claude-sonnet-5-5        # bounded extraction, reconciliation suggestions
LLM_MODE=replay                         # live | record | replay
OPENAI_API_KEY=                         # only if the OpenAI adapter is added
PORT=8000
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_BASE=http://localhost:8000/api
NCBI_API_KEY= / NCBI_EMAIL=             # pipeline only
MUJOCO_GL=glfw                          # replay rendering on macOS
```

## 5. Deployment

Backend Docker image bakes in `data/build/`, `data/llm_cache/`, and pre-rendered simulation
reports/replays (the browser shows recorded replays, labelled as such — live MuJoCo in the browser
is not P0). Frontend on Vercel; backend on Render/Fly. `GET /api/meta` exposes dataset version,
source versions, counts by source type / review state, and the cached-output flag.
