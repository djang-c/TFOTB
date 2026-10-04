"""One research run: find credible papers, extract claims, store them, log what happened.

Shared by `scripts/ingest_papers.py` and the API's on-demand research jobs, so both behave the same.
The standing policy (`config/ingest_policy.json`) is the only authority on what may run: how many
papers, how long a text, and whether a live model call is allowed at all. A run never raises for a
single bad paper; each paper's outcome is a row in the returned summary and in the run log.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.db import AtlasDB, export_snapshot
from atlas.discovery import DiscoveryError, Found, discover
from atlas.llm.base import LLMClient
from atlas.pipeline import ingest_papers, ledger_rows
from atlas.policy import IngestPolicy
from atlas.resolver import Resolver
from atlas.sources import FullText, fetch_full_text


class ResearchUnavailable(RuntimeError):
    """The reference files extraction needs (GO, ChEBI) are not on this machine."""


def load_extraction_resolver(raw_dir: Path) -> Resolver:
    needed = [raw_dir / "go" / "go-basic.json", raw_dir / "chebi" / "chebi_lite.json", raw_dir / "mondo" / "mondo.json"]
    missing = [str(p.relative_to(raw_dir)) for p in needed if not p.exists()]
    if missing:
        raise ResearchUnavailable(
            f"reading papers needs reference files that are not on this server: {', '.join(missing)} "
            "(run scripts/fetch_ontologies.py)"
        )
    return Resolver.from_raw(raw_dir, include_extraction_refs=True)


def already_ingested(store_dir: Path) -> set[str]:
    log = store_dir / "ingest_log.jsonl"
    if not log.exists():
        return set()
    rows = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    return {r["source_id"] for r in rows if r.get("status") == "ingested"}


def live_allowed(policy: IngestPolicy, *, offline: bool = False) -> bool:
    """A paid model call needs the policy to allow it AND a key in the environment."""
    return policy.live_extraction and not offline and bool(os.environ.get("ANTHROPIC_API_KEY"))


def run_research(
    *,
    terms: Iterable[str],
    pmids: list[str] | None,
    policy: IngestPolicy,
    store_dir: Path,
    client: LLMClient,
    resolver: Resolver,
    live: bool,
    discover_fn: Callable[..., list[Found]] = discover,
    fetch: Callable[[str], FullText] = fetch_full_text,
) -> dict[str, Any]:
    """Discover (unless `pmids` is given), ingest up to the policy's cap, log, snapshot, summarise."""
    store_dir.mkdir(parents=True, exist_ok=True)
    done = already_ingested(store_dir)
    found: list[Found] = []
    if pmids is None:
        try:
            found = discover_fn([t for t in terms if t], per_query=policy.discovery_per_query)
        except DiscoveryError as exc:
            return {"live": live, "discovered": 0, "new_papers": 0, "papers": [], "claims_added": 0,
                    "statements_quarantined": 0, "snapshot_rows": {}, "error": str(exc)}
        pmids = [f.pmid for f in found if f"PMID:{f.pmid}" not in done]
    db = AtlasDB(store_dir / "atlas.db")
    try:
        report = ingest_papers(
            pmids, client=client, resolver=resolver, db=db, allowed_licences=policy.only_licences,
            max_papers=policy.max_papers_per_run, max_chars=policy.max_chars_per_paper, skip=done, fetch=fetch,
        )
        now = datetime.now(UTC).isoformat(timespec="seconds")
        rows = ledger_rows(report)
        with (store_dir / "ingest_log.jsonl").open("a") as f:
            for row in rows:
                if row["reason"].startswith("per-run cap"):
                    continue  # not attempted this run; it stays in the summary but not in the log
                f.write(json.dumps({"at": now, **row}) + "\n")
        manifest = export_snapshot(db, store_dir / "snapshot", dataset_version=f"local-{now[:10]}", built_at=now)
    finally:
        db.close()
    return {
        "live": live,
        "discovered": len(found),
        "new_papers": len(pmids),
        "papers": rows,
        "claims_added": sum(r["claims_added"] for r in rows),
        "statements_quarantined": sum(r["statements_quarantined"] for r in rows),
        "snapshot_rows": {k: v["rows"] for k, v in manifest["files"].items()},
    }
