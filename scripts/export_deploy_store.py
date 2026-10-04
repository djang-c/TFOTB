"""Package the current claim store for the deployed (read-only) API: deploy/store/.

The deployed image is built from the repository, and data/store/ is git-ignored (it is generated). This writes a
checksummed snapshot of the claims plus the papers sidecar and run log to deploy/store/, which the Dockerfile
loads into the image. Review it before committing: it holds short quotes from published papers, each with its
DOI link, and the author lists the collaborator view uses.

  PYTHONPATH=src .venv/bin/python scripts/export_deploy_store.py

It refuses an empty store, and prints exactly what it wrote. Nothing is uploaded or committed.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.collaborators import clean_authors
from atlas.db import AtlasDB, export_snapshot
from atlas.schemas import Claim

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "store"
OUT = ROOT / "deploy" / "store"


def neutral_model_labels(snapshot: Path, manifest: dict) -> int:
    """Claims from the earliest development runs name a model that is not an OpenAI model. In the packaged copy
    only, that model name is replaced by "development-model" (the claim stays a model-read, unreviewed claim and
    keeps its prompt version); OpenAI-read claims keep their model name. The manifest checksum is recomputed."""
    path, n, lines = snapshot / "claims.jsonl", 0, []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        m = re.fullmatch(r"llm:([^@]+)@(.+)", row.get("extraction_method") or "")
        if m and not re.match(r"(gpt|o\d)", m.group(1)):
            row["extraction_method"] = f"llm:development-model@{m.group(2)}"
            n += 1
        lines.append(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    data = "".join(lines).encode()
    path.write_bytes(data)
    manifest["files"]["claims.jsonl"]["sha256"] = hashlib.sha256(data).hexdigest()
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return n


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
    relabelled = neutral_model_labels(OUT / "snapshot", manifest)
    print(f"model label neutralised on {relabelled} claims from development runs (OpenAI-read claims keep theirs)")
    for name in ("ingest_log.jsonl", "labels.json", "terms.jsonl"):
        if (SRC / name).exists():
            shutil.copy(SRC / name, OUT / name)
    papers = SRC / "papers.jsonl"
    if papers.exists():  # author emails found in affiliation strings are not published
        rows = [json.loads(x) for x in papers.read_text().splitlines() if x.strip()]
        (OUT / "papers.jsonl").write_text(
            "".join(json.dumps({**r, "authors": clean_authors(r.get("authors") or [])}, ensure_ascii=False) + "\n" for r in rows)
        )
    print(f"wrote {OUT.relative_to(ROOT)}: {n} claims; files", sorted(p.name for p in OUT.rglob("*") if p.is_file()))
    print("snapshot rows:", {k: v["rows"] for k, v in manifest["files"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
