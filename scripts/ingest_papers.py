"""Find and ingest papers into the persistent claim store (the local form of the weekly job).

  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py            # discover new papers, ingest them
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --dry-run  # show what it would do, spend nothing
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --pmids 37245481
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --query "Niemann-Pick type C lysosome"   # research on demand
  PYTHONPATH=src .venv/bin/python scripts/ingest_papers.py --entity MONDO:0018982

Only credible sources are used: PubMed-indexed journal articles with open-access full text. Preprints,
retractions, editorials and records without a journal are rejected, and each claim cites the paper's own
DOI link taken from its record.

What may run unattended is set once in config/ingest_policy.json (live model calls on/off, caps on
papers per run and text size, which diseases to watch). No per-run approval is needed. A live call
happens only if the policy allows it and OPENAI_API_KEY and OPENAI_MODEL_FAST are in the environment; otherwise recorded
responses are replayed and papers without one are reported as skipped.

Stored claims are `unreviewed` and immutable; review is an optional label upgrade, never a gate.
Outputs: data/store/atlas.db, data/store/snapshot/, data/store/ingest_log.jsonl.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlas.discovery import DiscoveryError, discover
from atlas.llm.cache import CachedClient
from atlas.llm.factory import make_client, provider_name
from atlas.policy import load_policy
from atlas.research import already_ingested, live_allowed, load_extraction_resolver, run_research
from atlas.terms import TermStore

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "store"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pmids", nargs="*", default=[], help="ingest these instead of discovering")
    ap.add_argument("--query", action="append", default=[], help="research this topic now (repeatable)")
    ap.add_argument("--entity", action="append", default=[], help="research this ontology ID now (repeatable)")
    ap.add_argument("--policy", type=Path, default=ROOT / "config" / "ingest_policy.json")
    ap.add_argument("--dry-run", action="store_true", help="list the papers it would ingest; fetch and spend nothing")
    ap.add_argument("--offline", action="store_true", help="never make a live model call this run")
    args = ap.parse_args()

    policy = load_policy(args.policy)
    resolver = load_extraction_resolver(ROOT / "data" / "raw")
    pmids = list(args.pmids)
    if not pmids:
        on_demand = bool(args.query or args.entity)  # the user asked for specific research: use only that
        terms = [resolver.label_of(e) for e in (args.entity if on_demand else policy.seed_entities)]
        terms += args.query if on_demand else list(policy.extra_queries)
        if not on_demand:  # terms that visitors looked up and that passed verification (atlas.terms) are watched too
            terms += [row["label"] for row in TermStore(STORE).all()]
        try:
            found = discover([t for t in terms if t], per_query=policy.discovery_per_query)
        except DiscoveryError as exc:
            print(f"{exc}\nNothing was ingested; run again later.")
            return 1
        done = already_ingested(STORE)
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

    live = live_allowed(policy, offline=args.offline)
    if policy.live_extraction and not args.offline and not live:
        print("Policy allows live calls but the API key for the chosen provider is not in the environment: replay-only this run.")
    inner = make_client(max_tokens=policy.max_output_tokens) if live else None
    client = CachedClient(inner, ROOT / "data" / "cache" / "llm", mode="replay", allow_live_on_miss=live, provider=provider_name())
    summary = run_research(
        terms=[], pmids=pmids, policy=policy, store_dir=STORE, client=client, resolver=resolver, live=live
    )
    for r in summary["papers"]:
        extra = f" +{r['claims_added']} claims, {r['statements_quarantined']} quarantined" if r["status"] == "ingested" else ""
        print(f"{r['source_id']}: {r['status']}" + (f" ({r['reason']})" if r["reason"] else "") + extra)
    print("snapshot rows:", summary["snapshot_rows"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
