# 10 — Testing & Verification

Implements: T13. **PLAN's "Release checks" table is the acceptance spec** — this doc adds the test
layers around it. BACKLOG lists which PLAN checks already have tests.

| Layer | What | Tooling |
|---|---|---|
| Schema | Existing `test_schemas.py` + new Entity/Coverage/Gap/Asset/ActionCard fixtures; SQLite round-trip | pytest |
| Resolver | Label-built IDs rejected; ambiguous synonyms unresolved; transcript versions not merged | pytest |
| Pipeline | `validate.py`: ID provenance, quote verification, lineage present, licence-manifest gate, synthetic isolation | pytest + report |
| Channels | Doc 05 §9 + missing ≠ zero (existing) + direction block (existing) | pytest |
| API | Contract tests on every endpoint; PLAN fixture cases end-to-end; private case never reachable from public endpoints | pytest + TestClient |
| LLM | Replay-mode, network off; validators drop ungrounded/uncited sentences; refusal handling; cached label set | pytest, `LLM_MODE=replay` |
| Actions | Footnotes resolve to claims; `responsible_human` set; dosing/eligibility denylist | pytest |
| Robotics | Existing `robotics/tests` (valid + 4 failing fixtures, reproducibility) + SimulationRun linkage | pytest |
| Frontend | typecheck, lint, build | tsc, eslint, next build |
| E2E | Journey A, Journey B, simulation report panel; zero console errors | Playwright |
| Perf | p95 < 2 s cached graph results (PLAN) | timing script |

Missing PLAN checks to add (per BACKLOG): assay incompatibility, honest gap, action traceability.

## Human checkpoints

1. **Evidence audit** (T01 gate, H3; again H20): a reviewer checks every positive path and the
   counterexample against sources. If no qualified reviewer is available, claims stay `unreviewed`
   and the README says so (PLAN: disclose absence rather than imply review).
2. **Copy test:** someone outside the team can tell observations from hypotheses.
3. **Overclaim pass** on README/video: measured 10× numbers only; cached/synthetic/recorded labels.

## Definition of done

- [ ] Journey A and B and the simulation report run on the deployed URL.
- [ ] 100% provenance completeness on displayed claims; zero invented-citation/privacy/unsupported-treatment failures in the fixture suite.
- [ ] All PLAN release checks have a passing test or a stated reason.
- [ ] README: architecture, dataset reproduction, source/licence manifest, 10× method + measured result, limitations.
- [ ] Team video + 1-minute walkthrough.
