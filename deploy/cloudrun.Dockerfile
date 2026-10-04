# TFOTB on Google Cloud Run: ONE service that serves the API and the built web app from the same address, so there is
# no separate front-end host and no cross-origin setup. Read-only: it serves the baked-in data, and anything written at
# runtime is lost when the instance stops. No OpenAI key is baked in: the AI features (paper reading, AI review of failed
# experiment runs) stay off here and work when someone runs the repo locally with their own key.
# Built from the folder made by scripts/assemble_cloudrun.py.

# ---- stage 1: the web app, built to use the API at the same address ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
# the build crawls its own preview server on localhost; inside Docker that must resolve to IPv4
ENV VITE_API_BASE=/api \
    NODE_OPTIONS=--dns-result-order=ipv4first
RUN npm run build

# ---- stage 2: the API ----
FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Pinned deps from the lockfile minus rendering and dev tools. MuJoCo stays: the Simulation page's plan check runs it.
COPY requirements.lock ./
RUN grep -viE '^(glfw|PyOpenGL|ImageIO|imageio-ffmpeg|pytest|ruff|iniconfig|pluggy|Pygments)==' \
        requirements.lock > requirements.api.txt \
    && pip install --no-cache-dir -r requirements.api.txt

COPY --chown=user src ./src
COPY --chown=user data/fixtures ./data/fixtures
COPY --chown=user config ./config
COPY --chown=user robotics ./robotics
COPY --chown=user deploy_store ./deploy_store
COPY --chown=user scripts/load_deploy_store.py ./scripts/load_deploy_store.py
RUN PYTHONPATH=src python scripts/load_deploy_store.py && chown -R user data

# Reference files: fetched from their publishers and verified against the recorded SHA-256 (any mismatch fails the
# build). --core leaves out GO and ChEBI, which only paper reading uses.
COPY --chown=user data/raw/CHECKSUMS.json ./data/raw/CHECKSUMS.json
COPY --chown=user scripts/fetch_for_deploy.py ./scripts/fetch_for_deploy.py
RUN python scripts/fetch_for_deploy.py --core && chown -R user data/raw

# Fail the build, not the demo, if the motion check cannot run in this image.
RUN PYTHONPATH=src python -c "from atlas import experiment as ex; p = ex.plan(ex.example_definition()); assert p['robot'], p['checks']"

COPY --from=web --chown=user /web/dist/client ./web

USER user
ENV PYTHONPATH=/home/user/app/src \
    FRONTEND_DIST=/home/user/app/web \
    PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn atlas.api.app:app --host 0.0.0.0 --port ${PORT}"]
