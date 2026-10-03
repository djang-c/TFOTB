"""Run T04 extraction on ONE paper with a real model call, record the response, and print the result.

This is the first live call in the project. It is guarded:
- it refuses to run unless --i-approve-sending-this-text is passed (the text leaves this machine);
- input is capped by --max-chars and output by --max-tokens, so cost is bounded, not estimated;
- the response is recorded in data/cache/llm (git-ignored) so every later run replays it offline;
- nothing is written to a store: claims are printed and discarded.

Usage (the key must be in the environment; this script never reads .env itself):
    set -a; source .env; set +a
    PYTHONPATH=src .venv/bin/python scripts/live_extract_once.py --source-id PMID:37245481 \\
        --url https://pmc.ncbi.nlm.nih.gov/articles/PMC10224778/ --text-file /path/to/paper.txt \\
        --i-approve-sending-this-text
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from atlas.extraction import PROMPT_VERSION, SourceText, extract_claims
from atlas.llm.anthropic_client import AnthropicClient
from atlas.llm.cache import CachedClient
from atlas.resolver import Resolver
from atlas.store import PublicStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--text-file", type=Path, required=True)
    ap.add_argument("--max-chars", type=int, default=60_000, help="refuse longer input (bounds input cost)")
    ap.add_argument("--max-tokens", type=int, default=4096, help="output cap sent to the API")
    ap.add_argument("--i-approve-sending-this-text", action="store_true")
    args = ap.parse_args()

    if not args.i_approve_sending_this_text:
        print("Refusing: pass --i-approve-sending-this-text to confirm this text may be sent to the provider.")
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Refusing: ANTHROPIC_API_KEY is not in the environment.")
        return 2
    text = args.text_file.read_text()
    if len(text) > args.max_chars:
        print(f"Refusing: text is {len(text)} chars, over --max-chars {args.max_chars}.")
        return 2

    client = CachedClient(AnthropicClient(max_tokens=args.max_tokens), ROOT / "data" / "cache" / "llm", mode="record")
    resolver = Resolver.from_raw(ROOT / "data" / "raw")
    report = extract_claims(client, SourceText(args.source_id, args.url, text), resolver)

    print(f"status={report.status} prompt={PROMPT_VERSION} reason={report.reason!r}")
    print(f"claims={len(report.claims)} quarantined={len(report.quarantined)}")
    for c in report.claims:
        print(f"  CLAIM {c.claim_id}: {c.subject_id} -[{c.predicate}]-> {c.object_id} | status={c.status}")
    for q in report.quarantined:
        print(f"  QUARANTINED: {q}")
    store = PublicStore()
    print("store ingest (in memory, discarded):", store.ingest_extraction(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
