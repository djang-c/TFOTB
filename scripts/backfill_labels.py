"""Write data/store/labels.json: names for every entity that the stored claims mention.

GO compartments and ChEBI chemicals are not in the public search index, so without this the graph and the
routes show raw IDs ("GO:0005764") instead of "lysosome". Only labels the pinned ontologies give are written.
Makes no network call and no model call. Safe to rerun.

  PYTHONPATH=src .venv/bin/python scripts/backfill_labels.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from atlas.api.claimstore import load_claims
from atlas.research import load_extraction_resolver, write_labels

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "store"


def main() -> int:
    claims = load_claims(STORE / "atlas.db")
    if not claims:
        print("No claims in the store.")
        return 2
    ids = {i for c in claims.values() for i in (c.subject_id, c.object_id, c.context.get("substance")) if i}
    n = write_labels(STORE, ids, load_extraction_resolver(ROOT / "data" / "raw"))
    print(f"{len(ids)} entities in {len(claims)} claims; labels.json now holds {n} names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
