"""Ingest papers into the persistent claim store (the local form of the weekly job; docs/DATABRICKS.md).

By default this makes NO paid call: it serves recorded model responses and skips any paper without one.
A live call needs all of: --live, --i-approve-sending-these-texts and ANTHROPIC_API_KEY.

  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --pmids 37245481 --allow-licence "cc by-nc-nd"

Papers whose licence is not on the allow-list are skipped and logged, never sent. Stored claims are
`unreviewed` and immutable. Outputs: data/store/atlas.db, data/store/snapshot/, data/store/ingest_log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.db import AtlasDB, export_snapshot
from atlas.llm.anthropic_client import AnthropicClient
from atlas.llm.cache import CachedClient
from atlas.pipeline import DEFAULT_ALLOWED_LICENCES, ingest_papers, ledger_rows
from atlas.resolver import Resolver

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "store"


def _already_done() -> set[str]:
    log = STORE / "ingest_log.jsonl"
    if not log.exists():
        return set()
    rows = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    return {r["source_id"] for r in rows if r["status"] == "ingested"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pmids", nargs="*", default=[], help="PubMed IDs")
    ap.add_argument("--watchlist", type=Path, help="text file, one PMID per line")
    ap.add_argument("--allow-licence", action="append", help="add a licence to the allow-list (repeatable)")
    ap.add_argument("--max-papers", type=int, default=5)
    ap.add_argument("--max-chars", type=int, default=70_000)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--live", action="store_true", help="allow a paid call on a cache miss")
    ap.add_argument("--i-approve-sending-these-texts", action="store_true")
    args = ap.parse_args()

    pmids = list(args.pmids)
    if args.watchlist:
        pmids += [x.strip() for x in args.watchlist.read_text().splitlines() if x.strip() and not x.startswith("#")]
    if not pmids:
        print("Nothing to do: give --pmids or --watchlist.")
        return 2
    if args.live and not (args.i_approve_sending_these_texts and os.environ.get("ANTHROPIC_API_KEY")):
        print("Refusing --live: it needs --i-approve-sending-these-texts and ANTHROPIC_API_KEY in the environment.")
        return 2

    inner = AnthropicClient(max_tokens=args.max_tokens) if args.live else None
    client = CachedClient(inner, ROOT / "data" / "cache" / "llm", mode="replay", allow_live_on_miss=args.live, provider="anthropic")
    resolver = Resolver.from_raw(ROOT / "data" / "raw", include_extraction_refs=True)
    STORE.mkdir(parents=True, exist_ok=True)
    db = AtlasDB(STORE / "atlas.db")
    allowed = [*DEFAULT_ALLOWED_LICENCES, *(args.allow_licence or [])]
    report = ingest_papers(
        pmids, client=client, resolver=resolver, db=db, allowed_licences=allowed,
        max_papers=args.max_papers, max_chars=args.max_chars, skip=_already_done(),
    )
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with (STORE / "ingest_log.jsonl").open("a") as f:
        for row in ledger_rows(report):
            f.write(json.dumps({"at": now, **row}) + "\n")
    for r in report.runs:
        print(f"{r.source_id}: {r.status}" + (f" ({r.reason})" if r.reason else "")
              + (f" +{r.claims_added} claims, {r.statements_quarantined} quarantined" if r.status == "ingested" else ""))
    manifest = export_snapshot(db, STORE / "snapshot", dataset_version=f"local-{now[:10]}", built_at=now)
    print("snapshot rows:", {k: v["rows"] for k, v in manifest["files"].items()})
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
