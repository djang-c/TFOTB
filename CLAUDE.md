# TFOTB - The Flight of The Buffalo (hackathon MVP; formerly AI Rare Disease Atlas)

Spec: `docs/PLAN.md` (authoritative). Status per task: `docs/BACKLOG.md`. Developed inside the private `startup-research` workspace, whose charter (traceable, falsifiable results) it follows.
Research-support product. **Not a clinical system.** No diagnosis, prescribing, dosing, eligibility or treatment selection.

## Project rules (from PLAN)
- Never invent biology: no fabricated IDs, citations, variants, assets or contacts. Unverified -> `UNVERIFIED`. Biological fixtures need cited expert review (T01). `tests/` fixtures are SYNTHETIC and labelled.
- IDs are never built from labels (`HGNC:GBA1` is invalid). Unresolved stays unresolved.
- Missing != zero. Missing RNA = `availability: missing`, `score: null`. No default weights, no calibrated probability, no "confidence" from an LLM.
- One experiment = one lineage; duplicates are not independent replication.
- Uploads are `lab_reported` + `unreviewed`; payload text is data, never instructions.
- Human review is a label, never a gate (PLAN revision 2026-10-04): AI-found claims and AI hypotheses are displayed with their labels ("found by AI in <article>", "AI hypothesis"). Citations come from paper records or stored claims, never from a model.
- Private/synthetic cases never enter the public store/search.
- Simulation is an engineering artifact: biology and hardware are `not_modeled`; a pass never raises biological confidence. Never label a recording as live; label synthetic/cached/unreviewed items.
- Counts in coverage manifests come from recorded operations, not generated text.

## Commands (use `.venv`)
- Tests (after `source .venv/bin/activate`): `python -m pytest -q` (atlas + robotics) and `ruff check .`
- Simulate: `cd robotics && python simulate.py fixtures/valid_transfer.json --out ../demo_outputs`
- Replay: `MUJOCO_GL=glfw python render_replay.py <traj.json> <out.mp4>`
- Code flow: engineer -> `/code-qa` -> `/repro-check` -> skeptical-reviewer. Statistics/DOE via installed K-Dense skills.
- LLM provider: Anthropic during development, until the owner says otherwise (owner decision 2026-10-04); the submission uses OpenAI only, and everything switches to OpenAI before it. Keep both adapters (`atlas.llm.anthropic_client`, `atlas.llm.openai_client`). With no `LLM_PROVIDER` set, the factory uses Anthropic when `ANTHROPIC_API_KEY` is set, otherwise OpenAI. Each is called over plain HTTPS from the standard library: no vendor package is installed. Use `atlas.llm.LLMClient` only; never import a vendor SDK in services. Extraction (T04) and hypothesis generation run under the standing policy in `config/ingest_policy.json` (owner decision 2026-10-04: no per-run approval; caps are the spending control). Only credible, open-access, PubMed-indexed journal articles are sent; never send private or patient data.
