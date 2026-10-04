# The Flight of the Buffalo API image for Hugging Face Spaces (Docker SDK). Read-only: serves the baked-in data;
# nothing written at runtime survives a restart. Built from the folder assembled by
# .github/workflows/deploy-api.yml (src/, data/fixtures/, data/raw/CHECKSUMS.json, scripts/fetch_for_deploy.py, requirements.lock).
FROM python:3.12-slim

# Spaces run the container as uid 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Pinned deps from the lockfile minus simulation/render and dev tools (not used by the API).
COPY requirements.lock ./
RUN grep -viE '^(mujoco|glfw|PyOpenGL|ImageIO|imageio-ffmpeg|pytest|ruff|iniconfig|pluggy|Pygments)==' \
        requirements.lock > requirements.api.txt \
    && pip install --no-cache-dir -r requirements.api.txt

COPY --chown=user src ./src
COPY --chown=user data/fixtures ./data/fixtures
COPY --chown=user config ./config
# The packaged claim store (scripts/export_deploy_store.py); the folder may be empty if none was packaged.
COPY --chown=user deploy_store ./deploy_store
COPY --chown=user scripts/load_deploy_store.py ./scripts/load_deploy_store.py
RUN PYTHONPATH=src python scripts/load_deploy_store.py && chown -R user data

# Real-ontology search: fetch the pinned reference files from their publishers at build time and
# verify them against the recorded SHA-256 (the build fails on any mismatch). ~190 MB.
COPY --chown=user data/raw/CHECKSUMS.json ./data/raw/CHECKSUMS.json
COPY --chown=user scripts/fetch_for_deploy.py ./scripts/fetch_for_deploy.py
RUN python scripts/fetch_for_deploy.py && chown -R user data/raw

USER user
# PYTHONPATH (not pip install) keeps REPO_ROOT in atlas.api.settings pointing at this folder.
ENV PYTHONPATH=/home/user/app/src \
    PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn atlas.api.app:app --host 0.0.0.0 --port ${PORT}"]
