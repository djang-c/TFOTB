# TFOTB API image for Hugging Face Spaces (Docker SDK). Read-only: serves the baked-in data;
# nothing written at runtime survives a restart. Built from the folder assembled by
# .github/workflows/deploy-api.yml (src/, data/fixtures/, requirements.lock).
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

USER user
# PYTHONPATH (not pip install) keeps REPO_ROOT in atlas.api.settings pointing at this folder.
ENV PYTHONPATH=/home/user/app/src \
    PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn atlas.api.app:app --host 0.0.0.0 --port ${PORT}"]
