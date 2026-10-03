# TFOTB - The Flight of The Buffalo - hackathon workspace

Implements `docs/PLAN.md` (Hack-Nation challenge MVP): evidence-qualified rare-disease connections + a bounded MuJoCo workflow simulation. Research support only; not clinical.

## State of the build
Working and tested: evidence/claim schemas, channel registry, ranking gates, upload quarantine, public/private separation, and the robotics workflow (compile -> checks -> MuJoCo motion -> report -> replay) with one passing and four failing fixtures. See `docs/BACKLOG.md` for the honest task table.
Not built: any real biological data, ID resolution, ingestion, OpenAI extraction, API, UI. T01 (choose + verify a disease cluster) needs a human expert first.

## Run
```bash
cd hackathon/tfotb && source .venv/bin/activate
python -m pytest -q && ruff check .
cd robotics && python simulate.py fixtures/valid_transfer.json --out ../demo_outputs
```
Rebuild env: `python3 -m venv .venv && pip install -r requirements.lock`.

## Layout
`src/atlas/` engine - `tests/` - `robotics/` (scene, schema, fixtures, compiler, simulator, replay, tests) - `demo_outputs/` generated reports/replay (git-ignored, regenerate locally) - `data/manifests/` source audit - `docs/`.
