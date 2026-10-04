"""Run T04 extraction on ONE paper with a real model call, record the response, and print the result.

This is the first live call in the project. It is guarded:
- it refuses to run unless --i-approve-sending-this-text is passed (the text leaves this machine);
- input is capped by --max-chars and output by --max-tokens, so cost is bounded, not estimated;
- the response is recorded in data/cache/llm (git-ignored) so every later run replays it offline;
- nothing is written to a store: claims are printed and discarded.

Usage (the key must be in the environment; this script never reads .env itself):
    set -a; source .env; set +a
    PYTHONPATH=src .venv/bin/python scripts/live_extract_once.py --pmid 37245481 --i-approve-sending-this-text
    (or --source-id ID --url URL --text-file FILE for text you already have)

--pmid fetches clean open-access full text from Europe PMC (see atlas/sources.py) and prints the
licence it reports. The text is cached under data/cache/texts (git-ignored), never committed.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from atlas.extraction import PROMPT_VERSION, SourceText, extract_claims
from atlas.llm.cache import CachedClient
from atlas.llm.factory import has_key, make_client, provider_name
from atlas.resolver import Resolver
from atlas.sources import SourceError, fetch_full_text
from atlas.store import PublicStore

ROOT = Path(__file__).resolve().parents[1]


def _stage(reason: str) -> str:
    """Which check rejected the statement (so a 0-claim run shows WHERE the loss is)."""
    if reason.startswith("quote not found"):
        return "quote"
    if reason.startswith(("no allowed predicate", "needs a substance")) or " needs " in reason:
        return "predicate/types/substance"
    if reason.startswith("schema:") or reason == "duplicate statement":
        return "schema"
    return "name resolution"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pmid", help="fetch open-access full text from Europe PMC")
    ap.add_argument("--source-id")
    ap.add_argument("--url")
    ap.add_argument("--text-file", type=Path)
    ap.add_argument("--max-chars", type=int, default=60_000, help="refuse longer input (bounds input cost)")
    ap.add_argument("--max-tokens", type=int, default=4096, help="output cap sent to the API")
    ap.add_argument("--i-approve-sending-this-text", action="store_true")
    args = ap.parse_args()

    if not args.i_approve_sending_this_text:
        print("Refusing: pass --i-approve-sending-this-text to confirm this text may be sent to the provider.")
        return 2
    if not has_key():
        print("Refusing: no model key in the environment (OPENAI_API_KEY).")
        return 2
    if args.pmid:
        try:
            ft = fetch_full_text(args.pmid)
        except SourceError as exc:
            print(f"Refusing: {exc}")
            return 2
        text, source_id, url = ft.text, f"PMID:{args.pmid}", ft.url
        cache = ROOT / "data" / "cache" / "texts"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"PMID-{args.pmid}.txt").write_text(text)
        print(f"fetched {ft.pmcid}: {len(text)} chars, licence reported by Europe PMC: {ft.license}")
    elif args.text_file and args.source_id and args.url:
        text, source_id, url = args.text_file.read_text(), args.source_id, args.url
    else:
        print("Refusing: give --pmid, or all of --source-id, --url and --text-file.")
        return 2
    if len(text) > args.max_chars:
        print(f"Refusing: text is {len(text)} chars, over --max-chars {args.max_chars}.")
        return 2

    client = CachedClient(make_client(max_tokens=args.max_tokens), ROOT / "data" / "cache" / "llm", mode="record", provider=provider_name())
    resolver = Resolver.from_raw(ROOT / "data" / "raw", include_extraction_refs=True)
    report = extract_claims(client, SourceText(source_id, url, text), resolver)

    print(f"status={report.status} prompt={PROMPT_VERSION} reason={report.reason!r}")
    print(f"claims={len(report.claims)} quarantined={len(report.quarantined)}")
    stages = Counter(_stage(q["reason"]) for q in report.quarantined)
    proposed = len(report.claims) + len(report.quarantined)
    print(
        f"yield: proposed {proposed} -> quote verified {proposed - stages['quote']} -> "
        f"types ok {proposed - stages['quote'] - stages['predicate/types/substance']} -> "
        f"names resolved {len(report.claims) + stages['schema']} -> stored {len(report.claims)}"
    )
    print("lost at each stage:", dict(stages) or "none")
    for c in report.claims:
        print(f"  CLAIM {c.claim_id}: {c.subject_id} -[{c.predicate}]-> {c.object_id} | status={c.status}")
    for q in report.quarantined:
        print(f"  QUARANTINED: {q}")
    store = PublicStore()
    print("store ingest (in memory, discarded):", store.ingest_extraction(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
