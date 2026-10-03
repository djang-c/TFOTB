# Implementation Plan (build-level detail)

`docs/PLAN.md` is the authoritative spec; `docs/BACKLOG.md` tracks task status. These docs add
build-level detail per T-task — schemas, endpoints, pipeline steps, channel algorithms, UI, prompts
for builder agents. **Where they disagree with PLAN, PLAN wins**; proposed deviations are listed in
[11 — Risks & open questions](11-risks-and-open-questions.md#proposed-decisions-from-builder-bs-planning-session--need-teammate-agreement-in-this-pr).

| # | Doc | Covers |
|---|---|---|
| 01 | [Scope, demo & 10×](01-scope-and-demo.md) | Seed slice candidate, demo journeys, 10× measurement |
| 02 | [Architecture](02-architecture.md) | Stack, layout additions, config, deploy |
| 03 | [Data & API contracts](03-data-contracts.md) | T02 additions, UI display mapping, HTTP API |
| 04 | [Data pipeline](04-data-pipeline.md) | T01 tooling, T03, T04 — reproducible build |
| 05 | [Channels & graph queries](05-graph-analytics.md) | T06–T09, paths, collaborators, optional T18 |
| 06 | [AI layer](06-ai-layer.md) | Bounded extraction, reconciliation suggestions, grounded explanation |
| 07 | [Action cards & simulation binding](07-action-engine.md) | T10, T17, T20/T23 |
| 08 | [Frontend & UX](08-frontend-ux.md) | T12, UI for T10/T11/T23 |
| 09 | [Phases (2 builders)](09-implementation-phases.md) | Timeline, cuts, agent prompts per T-task |
| 10 | [Testing & verification](10-testing-and-verification.md) | T13 |
| 11 | [Risks & open questions](11-risks-and-open-questions.md) | Risks, proposed decisions, open questions |
| 12 | [Breadth layer](12-breadth-layer.md) | All-disease corpus + verified depth slice; ML channel rules; T25–T27 |
