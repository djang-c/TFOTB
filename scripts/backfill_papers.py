"""Write data/store/papers.jsonl for papers ingested before author lists were recorded.

Reads the ingest log, asks Europe PMC (public, read-only, free) for each ingested paper's record, and appends
title, journal, year, DOI and the author list exactly as the record gives them. Safe to rerun: rows are keyed
by paper and the latest wins. Makes no model call.

  PYTHONPATH=src .venv/bin/python scripts/backfill_papers.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

from atlas.collaborators import load_papers
from atlas.research import already_ingested
from atlas.sources import API, SourceError, _get, authors_of, credibility_problem

STORE = Path(__file__).resolve().parent.parent / "data" / "store"


def main() -> int:
    have = load_papers(STORE)
    todo = sorted(already_ingested(STORE) - set(have))
    print(f"{len(have)} papers already have metadata; {len(todo)} to fetch")
    wrote = 0
    with (STORE / "papers.jsonl").open("a") as f:
        for sid in todo:
            pmid = sid.removeprefix("PMID:")
            q = urllib.parse.quote(f"EXT_ID:{pmid} AND SRC:MED")
            try:
                rec = json.loads(_get(f"{API}/search?query={q}&format=json&resultType=core"))["resultList"]["result"][0]
                if credibility_problem(rec):
                    raise SourceError(credibility_problem(rec))
            except (OSError, ValueError, IndexError, SourceError) as exc:
                print(f"  {sid}: skipped ({type(exc).__name__}: {exc})")
                continue
            doi = rec.get("doi", "")
            f.write(json.dumps({
                "source_id": sid, "pmid": pmid, "doi": doi, "title": rec.get("title", ""),
                "citation": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{pmid}",
                "journal": rec["journalInfo"]["journal"]["title"], "year": str(rec.get("pubYear", "")),
                "authors": list(authors_of(rec)),
            }) + "\n")
            wrote += 1
    print(f"wrote {wrote} rows to {STORE / 'papers.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
