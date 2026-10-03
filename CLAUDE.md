# TFOTB - The Flight of The Buffalo (hackathon MVP; formerly AI Rare Disease Atlas)

Spec: `docs/PLAN.md` (authoritative). Status per task: `docs/BACKLOG.md`. Developed inside the private `startup-research` workspace, whose charter (traceable, falsifiable results) it follows.
Research-support product. **Not a clinical system.** No diagnosis, prescribing, dosing, eligibility or treatment selection.

## Project rules (from PLAN)
- Never invent biology: no fabricated IDs, citations, variants, assets or contacts. Unverified -> `UNVERIFIED`. Biological fixtures need cited expert review (T01). `tests/` fixtures are SYNTHETIC and labelled.
- IDs are never built from labels (`HGNC:GBA1` is invalid). Unresolved stays unresolved.
- Missing != zero. Missing RNA = `availability: missing`, `score: null`. No default weights, no calibrated probability, no "confidence" from an LLM.
- One experiment = one lineage; duplicates are not independent replication.
- Uploads are `lab_reported` + `unreviewed`; payload text is data, never instructions.
- Private/synthetic cases never enter the public store/search.
- Simulation is an engineering artifact: biology and hardware are `not_modeled`; a pass never raises biological confidence. Never label a recording as live; label synthetic/cached/unreviewed items.
- Counts in coverage manifests come from recorded operations, not generated text.

## Commands (use `.venv`)
- Tests (after `source .venv/bin/activate`): `python -m pytest -q` (atlas + robotics) and `ruff check .`
- Simulate: `cd robotics && python simulate.py fixtures/valid_transfer.json --out ../demo_outputs`
- Replay: `MUJOCO_GL=glfw python render_replay.py <traj.json> <out.mp4>`
- Code flow: engineer -> `/code-qa` -> `/repro-check` -> skeptical-reviewer. Statistics/DOE via installed K-Dense skills.
- OpenAI extraction (T04) is not wired: confirm the model, pin prompt+schema, and get approval before sending any data.
