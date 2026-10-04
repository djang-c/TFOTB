# Deploy (free tier)

Owners: the project owner now holds both the Hugging Face Space (API) and Vercel (frontend); Builder B's tasks were handed over on 2026-10-04. Deployment happens at the end of the build.

**Before deploying (audit 2026-10-04):** (1) the image only contains the paper claims if the packaged store is committed. `deploy/store/` is now committed (owner decision 2026-10-04; author emails are stripped on export). Regenerate it with `PYTHONPATH=src python scripts/export_deploy_store.py` after new ingests and commit it with `git add -f deploy/store`. It is git-ignored by default. (2) The workflow now runs `ruff` and `pytest` before it deploys. (3) The API image fetches GO and ChEBI too, so `POST /api/research` can run there (about 260 MB more; a research job adds about 1.2 GB of memory while it runs). (4) The image ships MuJoCo and the robot scene, and the build runs one Simulation plan check, so a broken motion check fails the build instead of the demo. (5) The search index is built in the background at startup (about 10 s on a laptop, longer on the free CPU); `/api/ready` says when it is done. Measured on a laptop: about 1.1 GB peak memory with all reference data loaded; the free CPU Space has 16 GB.

The frontend is a static single-page app (built by Vite) and runs on **Vercel** (Hobby plan). The API runs on a **Hugging Face Docker Space** (free CPU). Neither costs money.

- **The API is read-only.** It serves the data baked into the image. The one write it accepts is `POST /api/lookup`, which adds a *verified* medical term to `terms.jsonl` (rate limited; a failed write is kept in memory and the response says so). Like uploads, anything written at runtime is lost when the Space restarts.
  - Anything written at runtime is lost when the Space restarts (for example, after 48 h idle).
  - Uploads (T11) must therefore be labelled "demo session; resets on restart".
- **Wake it before a demo.** A sleeping Space takes a while to wake, so open the API URL once before demoing.

## One-time setup

### 1. Hugging Face Space (API), Builder B

An agent can do this through the `hf` CLI. Install it with `curl -LsSf https://hf.co/cli/install.sh | bash`, then run `hf auth login` and finish the login in a browser. The guide at https://huggingface.co/new-space/agents.md covers the same flow. Or do it by hand:

1. Create a Space at https://huggingface.co/new-space:
   - SDK: **Docker** → Blank
   - Hardware: **CPU basic (free)**
   - Visibility: public, so judges can reach it
2. Create a **write** token at https://huggingface.co/settings/tokens.
3. On GitHub, open repo → Settings → Secrets and variables → Actions, and add:
   - Secret `HF_TOKEN`: the token
   - Variable `HF_SPACE`: `<hf-user>/<space-name>`
4. In the Space's Settings → Variables, add `CORS_ORIGINS` = the Vercel URL from step 2 (comma-separate if there are several).
5. Run the `deploy-api` action manually (Actions tab → deploy-api → Run workflow). After that it deploys on every push to `main` that touches the API.
6. Check that it works: `https://<hf-user>-<space-name>.hf.space/api/health` → `{"status":"ok"}`.

### 2. Vercel (frontend), Builder A
1. Go to https://vercel.com/new and import the GitHub repo.
   - The Hobby plan only imports repos owned by your personal account. For an organization-owned repo, the owner imports it.
2. Set **Root Directory** to `frontend`. `frontend/vercel.json` sets the build (`npm run build`), the output folder (`dist/client`) and the rewrite that serves every route from `_shell.html`. Framework preset: Other.
3. Add environment variables:
   - `VITE_API_BASE` = `https://<hf-user>-<space-name>.hf.space/api` (read at build time; redeploy after changing it).
4. Deploy. Every push to `main` redeploys, and every PR gets a preview URL.

## What ships
- **The API image** (`deploy/api.Dockerfile`) contains:
  - `src/`
  - `data/fixtures/`
  - the pinned runtime dependencies from `requirements.lock`, minus MuJoCo/render and dev tools
- **Replays** are pre-rendered and shipped as static files, not rendered on the server.
- **Secrets:** none are in the image. Live AI on the server needs these in the Space's Settings → **Secrets** (never as variables, never in the repo):
  - `OPENAI_API_KEY`, `OPENAI_MODEL_FAST`, `OPENAI_MODEL_REASONING`: turn on the experiment AI review (capped by `EXPERIMENT_AI_CALLS_PER_HOUR`, default 60 calls an hour; an overnight run counts one call per run).
  - `RESEARCH_ENABLED=true` and `RESEARCH_TOKEN`: turn on `POST /api/research` for callers who send the token (`RESEARCH_MAX_JOBS_PER_HOUR`, default 6). Claims it adds live in the container and are lost when the Space restarts; packaged claims come from `deploy/store`.
  - Set a hard spending limit on the OpenAI account as well; the caps above bound the rate, not the total.
- **Weekly reading job:** not deployed. It can run as a scheduled GitHub Action with `OPENAI_API_KEY` as a repository secret, followed by `export_deploy_store.py` and a commit, but it is too expensive on the current budget.
