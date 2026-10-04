"""Assemble the folder the Cloud Run image is built from (deploy/cloudrun.Dockerfile), into build/cloudrun by default.

    python scripts/assemble_cloudrun.py [OUT_DIR]
    gcloud run deploy tfotb --source build/cloudrun ...   (see docs/DEPLOY.md)

Copies only what the image needs: the API code, fixtures, config, the robot scene, the packaged claim store, the
front-end source, the lockfile and the two fetch/load scripts. No keys, no .env, no reference data files (the image
downloads and verifies those itself).
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "dist", ".vite", "e2e", ".DS_Store")
PINS = ROOT / "data" / "raw" / "CHECKSUMS.json"  # the recorded SHA-256 of each reference file


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "build" / "cloudrun"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(ROOT / "src", out / "src", ignore=SKIP)
    shutil.copytree(ROOT / "data" / "fixtures", out / "data" / "fixtures", ignore=SKIP)
    (out / PINS.relative_to(ROOT)).parent.mkdir(parents=True)
    shutil.copy(PINS, out / PINS.relative_to(ROOT))
    shutil.copytree(ROOT / "config", out / "config")
    rb = out / "robotics"
    rb.mkdir()
    for pattern in ("*.py", "*.json"):
        for f in (ROOT / "robotics").glob(pattern):
            shutil.copy(f, rb / f.name)
    shutil.copy(ROOT / "robotics" / "scene.xml", rb / "scene.xml")
    shutil.copytree(ROOT / "robotics" / "fixtures", rb / "fixtures")
    (rb / "render_replay.py").unlink(missing_ok=True)
    store = out / "deploy_store"
    store.mkdir()
    (store / ".keep").touch()
    if (ROOT / "deploy" / "store").is_dir():
        shutil.copytree(ROOT / "deploy" / "store", store, dirs_exist_ok=True)
    (out / "scripts").mkdir()
    for name in ("fetch_for_deploy.py", "load_deploy_store.py"):
        shutil.copy(ROOT / "scripts" / name, out / "scripts" / name)
    shutil.copytree(ROOT / "frontend", out / "frontend", ignore=SKIP)
    shutil.copy(ROOT / "requirements.lock", out / "requirements.lock")
    shutil.copy(ROOT / "deploy" / "cloudrun.Dockerfile", out / "Dockerfile")
    now = time.time()  # gcloud zips the folder, and zip cannot store timestamps before 1980
    for f in [out, *out.rglob("*")]:
        os.utime(f, (now, now))
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) // 1024
    print(f"assembled {out} ({size} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
