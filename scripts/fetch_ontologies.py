"""Pipeline step 01: download pinned ontology files into data/raw/ and record SHA-256.

Files are git-ignored (large, third-party); data/raw/CHECKSUMS.json is tracked.
Re-running verifies existing files against the recorded hash and never overwrites.
"""
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
GH_HPO = "https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01"
FILES = {
    "mondo/mondo.json": ("https://github.com/monarch-initiative/mondo/releases/download/v2026-09-01/mondo.json", "MONDO v2026-09-01 (CC BY 4.0)"),
    "hpo/hp.json": (f"{GH_HPO}/hp.json", "HPO v2026-09-01 (custom licence; see source_manifest.md)"),
    "hpo/phenotype.hpoa": (f"{GH_HPO}/phenotype.hpoa", "HPO annotations v2026-09-01"),
    "hpo/genes_to_disease.txt": (f"{GH_HPO}/genes_to_disease.txt", "HPO gene-disease v2026-09-01"),
    "go/go-basic.json": ("https://current.geneontology.org/ontology/go-basic.json", "Gene Ontology go-basic release 2026-07-26 via the unversioned URL (CC BY 4.0, per the file header)"),
    "chebi/chebi_lite.json": ("https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi_lite.json", "ChEBI lite release 255 via the unversioned URL (CC BY 4.0, per the file header)"),
    "hgnc/hgnc_complete_set.txt": ("https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt", "HGNC complete set (CC0), unversioned; date = retrieval date"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest_path = RAW / "CHECKSUMS.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for rel, (url, note) in FILES.items():
        dest = RAW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if rel in manifest and sha256(dest) != manifest[rel]["sha256"]:
                print(f"HASH MISMATCH {rel}", file=sys.stderr)
                return 1
            print(f"present {rel}")
        else:
            print(f"downloading {rel}")
            req = urllib.request.Request(url, headers={"User-Agent": "tfotb-fetch/1.0 (research; contact via repo)"})
            with urllib.request.urlopen(req) as resp, dest.open("wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
            dest.chmod(0o444)
        manifest[rel] = {
            "url": url,
            "note": note,
            "sha256": sha256(dest),
            "bytes": dest.stat().st_size,
            "retrieved": manifest.get(rel, {}).get("retrieved", datetime.now(UTC).date().isoformat()),
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
