"""Generate AI hypotheses from the stored claims and store them, labelled as hypotheses.

  PYTHONPATH=src .venv/bin/python scripts/generate_hypotheses.py

Reads data/store/atlas.db, asks the model for links that two or more stored claims make plausible, keeps
only those that pass the grounding checks in src/atlas/hypotheses.py (real stored citations, entities
taken from the cited claims, hypothesis-only predicates), and stores them as `inference` /
`ai_generated` / `unreviewed`. No per-run approval: the standing policy (config/ingest_policy.json)
decides whether live calls are allowed; without a key it replays a recorded response or does nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.db import AtlasDB
from atlas.hypotheses import generate_hypotheses
from atlas.llm.anthropic_client import AnthropicClient
from atlas.llm.base import LLMError
from atlas.llm.cache import CachedClient
from atlas.policy import load_policy
from atlas.resolver import Resolver
from atlas.schemas import Claim

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "store"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", type=Path, default=ROOT / "config" / "ingest_policy.json")
    ap.add_argument("--offline", action="store_true", help="never make a live model call this run")
    args = ap.parse_args()

    policy = load_policy(args.policy)
    if not (STORE / "atlas.db").exists():
        print("No claim store yet: run scripts/ingest_papers.py first.")
        return 2
    live = policy.live_extraction and not args.offline and bool(os.environ.get("ANTHROPIC_API_KEY"))
    inner = AnthropicClient(max_tokens=policy.max_output_tokens) if live else None
    client = CachedClient(inner, ROOT / "data" / "cache" / "llm", mode="replay", allow_live_on_miss=live, provider="anthropic")
    resolver = Resolver.from_raw(ROOT / "data" / "raw", include_extraction_refs=True)
    db = AtlasDB(STORE / "atlas.db")
    claims = {c.claim_id: c for c in db.all(Claim)}
    try:
        report = generate_hypotheses(client, claims, label_of=resolver.label_of, max_hypotheses=policy.max_hypotheses_per_run)
    except LLMError as exc:
        print(f"No hypotheses generated: {exc}")
        return 0
    added = 0
    for c in report.claims:
        if db.get(Claim, c.claim_id) is None:
            db.put(c)
            added += 1
    log = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"), "kind": "hypotheses", "model": report.model,
        "prompt_version": report.prompt_version, "accepted": len(report.claims), "added": added,
        "rejected": report.rejected,
    }
    with (STORE / "ingest_log.jsonl").open("a") as f:
        f.write(json.dumps(log) + "\n")
    for c in report.claims:
        print(f"  HYPOTHESIS {c.claim_id}: {c.subject_id} -[{c.predicate}]-> {c.object_id} (from {', '.join(c.derived_from)})")
        print(f"      {c.source_span}")
    for r in report.rejected:
        print(f"  rejected: {r['reason']}")
    print(f"accepted {len(report.claims)}, newly stored {added}, rejected {len(report.rejected)}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
