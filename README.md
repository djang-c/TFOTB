# TFOTB - The Flight of The Buffalo

Hackathon submission (Hack-Nation Challenge 05). An evidence-backed rare-disease connection explorer, plus a bounded MuJoCo simulation of a lab liquid-handling workflow.
**Research support only. Not a clinical system.** No diagnosis, dosing, eligibility or treatment advice. Spec: [`docs/PLAN.md`](docs/PLAN.md). Task status: [`docs/BACKLOG.md`](docs/BACKLOG.md). Why things are the way they are: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## What it does
1. **Finds how rare diseases connect.** For a disease it lists related diseases and says how strong the evidence is. The label is the evidence category: *reviewed mechanistic lead*, *literature-supported lead*, *symptom-level lead*, *hypothesis only*, *conflicting evidence* or *insufficient coverage*. There is no combined score and no probability.
2. **Reads the literature by itself.** It finds credible papers (PubMed-indexed journal articles with open-access full text; preprints, retractions and editorials are rejected), has an AI model propose claims, and keeps a claim only if its quote appears word for word in the paper and its names resolve to real ontology IDs. Every claim cites the paper's own DOI link.
3. **Makes hypotheses and says so.** The AI may propose links no paper states. These are always labelled "AI hypothesis, not a finding", must cite at least two stored claims, and never count as evidence.
4. **Shows where everything came from.** Nothing needs human review to be displayed. Each claim says whether it was found by AI in a named article, is an AI hypothesis, or came from a database, and whether anyone reviewed it.
5. **Separates independent studies from background.** A paper that only cites a fact as already known adds a little weight, shown as its own number, but is not counted as an independent study.
6. **Says when it found nothing.** A gap is dated and limited to the indexed evidence. It never says "no connection exists".
7. **Simulates a workflow check.** A MuJoCo model checks a proposed plate-preparation sequence for resource and motion failures. A pass says nothing about biology.

## Verify it yourself
| Claim | How to check |
|---|---|
| The test suite passes | `make test` (367 tests on 2026-10-04) and `make lint` |
| The reference data is the pinned version | `python scripts/fetch_ontologies.py` re-verifies every file against `data/raw/CHECKSUMS.json` |
| Claims carry real citations and verbatim quotes | Open any paper-derived claim in the evidence drawer (it links the article and shows the quote), or run `scripts/ingest_papers.py --pmids 37245481` with an API key and inspect `data/store/`. Recorded model responses are not committed, so a run without a key makes no claims. |
| The simulation fails when it should | `cd robotics && python simulate.py fixtures/blocked_path.json --out ../demo_outputs` (expect: fail) |

## Quick start (any machine)
Toolchain is pinned in `mise.toml` (Python 3.12, Node 22, pnpm). Install [mise](https://mise.jdx.dev) once, then:

```bash
git clone https://github.com/djang-c/TFOTB.git && cd TFOTB
mise trust && make setup   # tools, .venv from requirements.lock, frontend deps, .env from env.example (all keys optional)
make test                  # pytest (atlas + robotics + API)
make dev                   # API :8000 + web :3000
```
Real reference data (about 440 MB, git-ignored) is downloaded with `python scripts/fetch_ontologies.py`. Without it the app runs on the clearly labelled SYNTHETIC demo data only.

### Reading papers (needs an Anthropic API key in `.env`)
```bash
PYTHONPATH=src python scripts/ingest_papers.py --dry-run                     # what it would read; spends nothing
PYTHONPATH=src python scripts/ingest_papers.py                               # discover and read new papers
PYTHONPATH=src python scripts/ingest_papers.py --query "Niemann-Pick type C" # research a topic now
PYTHONPATH=src python scripts/generate_hypotheses.py                         # AI hypotheses from stored claims
```
What may run unattended, and how many papers per run, is set in [`config/ingest_policy.json`](config/ingest_policy.json). Without a key nothing is sent and no paid call is made (it can only replay responses you recorded yourself). The API endpoint `POST /api/research` does the same on demand; it is off unless `RESEARCH_ENABLED=true`.

### Simulation
```bash
cd robotics
python simulate.py fixtures/valid_transfer.json --out ../demo_outputs      # expect: pass
python simulate.py fixtures/blocked_path.json --out ../demo_outputs        # expect: fail (intended)
```
Optional replay video: `MUJOCO_GL=glfw python render_replay.py ../demo_outputs/valid_transfer.trajectory.json ../demo_outputs/valid_transfer.replay.mp4` (needs OpenGL/GLFW and ffmpeg; not verified on a clean machine).

## Limits, stated plainly
- **No expert has reviewed any biological claim.** Labels, not review, are the protection. A reviewer can upgrade a claim's label; none has.
- **PubMed indexing is a proxy for peer review.** The code checks the paper's own record (a journal article, not a preprint, retraction or editorial). It does not verify peer review itself.
- **The AI can be wrong.** The quote check proves the sentence exists in the paper, not that the AI read it correctly. The "new finding versus background" label is also the AI's judgement.
- **The symptom-similarity number is a similarity, not a probability, and has not been validated against any ground truth.**
- **Small evidence base.** The seed cluster is CLN3 disease and Niemann-Pick type C. Results outside it come mostly from public reference files and are mostly symptom-level.
- **Licences.** This is a hackathon project, not a commercial use. Any open-access paper may be read; each paper's licence is recorded in the run log. HPO's commercial terms are unresolved (see `data/manifests/source_manifest.md`). Revisit all of this before any commercial use.
- **The simulation is a geometry and resource check.** No liquids, hardware, calibration or biology are modelled.

## Layout
`src/atlas/` engine (the Python package is still named `atlas`) · `frontend/` explorer UI · `config/` standing ingest policy · `scripts/` data and pipeline scripts · `robotics/` scene, schema, fixtures, compiler, simulator, replay · `tests/` · `data/manifests/` source audit · `docs/` plan, decisions, backlog, deploy notes.
