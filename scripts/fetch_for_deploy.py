"""Deploy step: download the reference files the API needs and verify each against the SHA-256
recorded in data/raw/CHECKSUMS.json. Any mismatch fails the build: an upstream file that changed
under an unversioned URL must be re-pinned on purpose (scripts/fetch_ontologies.py), never
picked up silently. Downloads straight from the original publishers; nothing is re-hosted.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
CORE = ("mondo/mondo.json", "hpo/hp.json", "hpo/phenotype.hpoa", "hpo/genes_to_disease.txt",
        "hgnc/hgnc_complete_set.txt")
# GO and ChEBI: only paper reading needs these (POST /api/research), ~260 MB more. `--core` leaves them out, for hosts
# where paper reading is not switched on (no OpenAI key): the search, dossiers and Simulation do not use them.
EXTRA = ("go/go-basic.json", "chebi/chebi_lite.json")
NEEDED = CORE + EXTRA


def main() -> int:
    manifest = json.loads((RAW / "CHECKSUMS.json").read_text())
    for rel in (CORE if "--core" in sys.argv[1:] else NEEDED):
        entry, dest = manifest[rel], RAW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {rel}", flush=True)
        req = urllib.request.Request(entry["url"], headers={"User-Agent": "tfotb-deploy/1.0 (research; contact via repo)"})
        h = hashlib.sha256()
        with urllib.request.urlopen(req) as resp, dest.open("wb") as out:
            while chunk := resp.read(1 << 20):
                h.update(chunk)
                out.write(chunk)
        if h.hexdigest() != entry["sha256"]:
            print(f"HASH MISMATCH {rel}: upstream changed; re-pin with scripts/fetch_ontologies.py", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
