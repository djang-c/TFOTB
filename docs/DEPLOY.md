# Deploy (free tier)

Owners: **Builder B owns the Hugging Face Space (API)** and **Builder A owns Vercel (frontend)**. Deployment happens at the end of the build.

The frontend runs on **Vercel** (Hobby plan). The API runs on a **Hugging Face Docker Space** (free CPU). Neither costs money.

- **The API is read-only.** It serves the data baked into the image.
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
2. Set **Root Directory** to `frontend`. The framework is auto-detected as Next.js.
3. Add environment variables:
   - `NEXT_PUBLIC_API_BASE` = `https://<hf-user>-<space-name>.hf.space/api`
   - `ENABLE_EXPERIMENTAL_COREPACK` = `1`. Corepack is Node's package-manager shim; this makes Vercel use the pnpm version pinned in `package.json` (`pnpm@12.8.2`).
4. Deploy. Every push to `main` redeploys, and every PR gets a preview URL.

## What ships
- **The API image** (`deploy/api.Dockerfile`) contains:
  - `src/`
  - `data/fixtures/`
  - the pinned runtime dependencies from `requirements.lock`, minus MuJoCo/render and dev tools
- **Replays** are pre-rendered and shipped as static files, not rendered on the server.
- **Secrets:** none are in the image. If the API later needs LLM keys, add them as Space **secrets**, never as variables. The read path is offline-first (`LLM_MODE=replay`).
