"""Build data/store/atlas.db inside the image from deploy_store/ (checksums are verified; a mismatch fails the build)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from atlas.db import load_snapshot

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "deploy_store"
DST = ROOT / "data" / "store"


def main() -> int:
    if not (SRC / "snapshot" / "manifest.json").exists():
        print("No packaged claim store in this build: the API will start with no paper claims.")
        return 0
    DST.mkdir(parents=True, exist_ok=True)
    if (DST / "atlas.db").exists():
        (DST / "atlas.db").unlink()
    db = load_snapshot(SRC / "snapshot", DST / "atlas.db")
    db.close()
    for name in ("papers.jsonl", "ingest_log.jsonl", "labels.json", "terms.jsonl"):
        if (SRC / name).exists():
            shutil.copy(SRC / name, DST / name)
    print("loaded the packaged claim store into", DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
