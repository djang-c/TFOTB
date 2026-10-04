"""Package the current claim store for the deployed (read-only) API: deploy/store/.

The deployed image is built from the repository, and data/store/ is git-ignored (it is generated). This writes a
checksummed snapshot of the claims plus the papers sidecar and run log to deploy/store/, which the Dockerfile
loads into the image. Review it before committing: it holds short quotes from published papers, each with its
DOI link, and the author lists the collaborator view uses.

  PYTHONPATH=src .venv/bin/python scripts/export_deploy_store.py

It refuses an empty store, and prints exactly what it wrote. Nothing is uploaded or committed.
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.db import AtlasDB, export_snapshot
from atlas.schemas import Claim

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "store"
OUT = ROOT / "deploy" / "store"


def main() -> int:
    if not (SRC / "atlas.db").exists():
        print("No claim store at data/store/atlas.db: run scripts/ingest_papers.py first.")
        return 2
    db = AtlasDB(SRC / "atlas.db")
    n = len(db.all(Claim))
    if n == 0:
        print("The store holds no claims; nothing to package.")
        return 2
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    manifest = export_snapshot(db, OUT / "snapshot", dataset_version=f"deploy-{now[:10]}", built_at=now)
    db.close()
    for name in ("papers.jsonl", "ingest_log.jsonl", "labels.json"):
        if (SRC / name).exists():
            shutil.copy(SRC / name, OUT / name)
    print(f"wrote {OUT.relative_to(ROOT)}: {n} claims; files", sorted(p.name for p in OUT.rglob("*") if p.is_file()))
    print("snapshot rows:", {k: v["rows"] for k, v in manifest["files"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
