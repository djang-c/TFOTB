"""Find and ingest papers into the persistent claim store (the local form of the weekly job).

  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py            # discover new papers, ingest them
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --dry-run  # show what it would do, spend nothing
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --pmids 37245481

What may run unattended is set once in config/ingest_policy.json (live model calls on/off, caps on
papers per run and text size, which diseases to watch). No per-run approval is needed. A live call
happens only if the policy allows it and ANTHROPIC_API_KEY is in the environment; otherwise recorded
responses are replayed and papers without one are reported as skipped.

Stored claims are `unreviewed` and immutable; review is an optional label upgrade, never a gate.
Outputs: data/store/atlas.db, data/store/snapshot/, data/store/ingest_log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.db import AtlasDB, export_snapshot
from atlas.discovery import discover
from atlas.llm.anthropic_client import AnthropicClient
from atlas.llm.cache import CachedClient
from atlas.pipeline import ingest_papers, ledger_rows
from atlas.policy import load_policy
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
    ap.add_argument("--pmids", nargs="*", default=[], help="ingest these instead of discovering")
    ap.add_argument("--policy", type=Path, default=ROOT / "config" / "ingest_policy.json")
    ap.add_argument("--dry-run", action="store_true", help="list the papers it would ingest; fetch and spend nothing")
    ap.add_argument("--offline", action="store_true", help="never make a live model call this run")
    args = ap.parse_args()

    policy = load_policy(args.policy)
    resolver = Resolver.from_raw(ROOT / "data" / "raw", include_extraction_refs=True)
    pmids = list(args.pmids)
    if not pmids:
        terms = [resolver.label_of(e) for e in policy.seed_entities] + list(policy.extra_queries)
        found = discover([t for t in terms if t], per_query=policy.discovery_per_query)
        done = _already_done()
        pmids = [f.pmid for f in found if f"PMID:{f.pmid}" not in done]
        print(f"discovered {len(found)} open-access papers, {len(pmids)} not yet ingested")
        if args.dry_run:
            for f in found[: policy.max_papers_per_run + 5]:
                mark = "new " if f.pmid in pmids else "done"
                print(f"  [{mark}] PMID:{f.pmid} ({f.query}) {f.title[:90]}")
            print(f"(a real run would take the first {policy.max_papers_per_run} new papers)")
            return 0
    elif args.dry_run:
        print("papers:", ", ".join(f"PMID:{p}" for p in pmids))
        return 0
    if not pmids:
        print("Nothing new to ingest.")
        return 0

    live = policy.live_extraction and not args.offline and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if policy.live_extraction and not args.offline and not live:
        print("Policy allows live calls but ANTHROPIC_API_KEY is not in the environment: replay-only this run.")
    inner = AnthropicClient(max_tokens=policy.max_output_tokens) if live else None
    client = CachedClient(inner, ROOT / "data" / "cache" / "llm", mode="replay", allow_live_on_miss=live, provider="anthropic")
    STORE.mkdir(parents=True, exist_ok=True)
    db = AtlasDB(STORE / "atlas.db")
    report = ingest_papers(
        pmids, client=client, resolver=resolver, db=db, allowed_licences=policy.only_licences,
        max_papers=policy.max_papers_per_run, max_chars=policy.max_chars_per_paper, skip=_already_done(),
    )
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with (STORE / "ingest_log.jsonl").open("a") as f:
        for row in ledger_rows(report):
            f.write(json.dumps({"at": now, **row}) + "\n")
    for r in report.runs:
        extra = f" +{r.claims_added} claims, {r.statements_quarantined} quarantined" if r.status == "ingested" else ""
        print(f"{r.source_id}: {r.status}" + (f" ({r.reason})" if r.reason else "") + extra)
    manifest = export_snapshot(db, STORE / "snapshot", dataset_version=f"local-{now[:10]}", built_at=now)
    print("snapshot rows:", {k: v["rows"] for k, v in manifest["files"].items()})
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
