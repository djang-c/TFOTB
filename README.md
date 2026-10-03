# TFOTB - The Flight of The Buffalo

Hackathon submission (Hack-Nation challenge MVP). Spec: [`docs/PLAN.md`](docs/PLAN.md). Task status: [`docs/BACKLOG.md`](docs/BACKLOG.md).
Evidence-qualified rare-disease connection engine + a bounded MuJoCo workflow simulation. **Research support only; not a clinical system.** Formerly "AI Rare Disease Atlas".

## What judges can verify today
| Component | Status | Evidence |
|---|---|---|
| Evidence/claim schemas, channel registry, ranking gates, upload quarantine, public/private separation | Working, unit-tested | `pytest`: 197 passed |
| Robotics workflow: compile -> checks -> MuJoCo motion -> report | Working; 1 passing + 4 failing fixtures (failures are the intended safety checks) | `robotics/simulate.py` |
| Replay video (`render_replay.py`) | Not verified on a clean machine; needs OpenGL/GLFW and ffmpeg | - |

## Not built (stated plainly)
Real biological data, ID resolution, ingestion, extraction service, API, UI. LLM provider: Anthropic for now, OpenAI adapter at deployment; only an offline-tested provider-agnostic client scaffold exists (`src/atlas/llm/`), and the Anthropic adapter has never been run. **No domain expert has reviewed any biological claim**: the CLN3 + NPC audit (`data/manifests/cluster_audit.md`) was drafted by AI agents and read against the source paper by a non-expert, so every claim stays `unreviewed` and hypothesis-level. All test fixtures are **SYNTHETIC**. The simulation is an engineering artifact: biology and hardware are `not_modeled`, and a pass never raises biological confidence.

## Quick start (any machine)
Toolchain is pinned in `mise.toml` (Python 3.12.15, Node 22.23.3, pnpm 12.8.2). Install [mise](https://mise.jdx.dev) once (`curl https://mise.run | sh`), then from a fresh clone:

```bash
git clone https://github.com/djang-c/TFOTB.git && cd TFOTB
mise trust && make setup   # tools, .venv from requirements.lock, frontend deps, .env from env.example (all keys optional)
make test                  # pytest (atlas + robotics + API)
make lint                  # ruff + eslint + tsc
make dev                   # API :8000 (stub fixtures, SYNTHETIC) + web :3000
```
Other targets: `make typegen` (OpenAPI -> `frontend/src/lib/api-types.ts`), `make e2e` (Playwright; first run `cd frontend && pnpm exec playwright install chromium`), `make lock` (re-freeze Python deps). Activate the venv for the commands below: `source .venv/bin/activate`.

Run the simulation (writes to `demo_outputs/`, which is git-ignored and created on first run):
```bash
cd robotics
python simulate.py fixtures/valid_transfer.json --out ../demo_outputs      # expect: pass
python simulate.py fixtures/blocked_path.json --out ../demo_outputs        # expect: fail (intended)
```
Optional replay video: `MUJOCO_GL=glfw python render_replay.py ../demo_outputs/valid_transfer.trajectory.json ../demo_outputs/valid_transfer.replay.mp4`

## Layout
`src/atlas/` engine (Python package name is still `atlas`) - `tests/` - `robotics/` (scene, schema, fixtures, compiler, simulator, replay, tests) - `data/manifests/` source audit (empty template) - `docs/`.
