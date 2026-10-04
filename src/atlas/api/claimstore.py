"""Read-only access to the persistent claim store (data/store/atlas.db, written by scripts/ingest_papers.py).

The API never writes here. The file is opened read-only, so a request cannot change the evidence, and
rows are re-validated as `Claim` on the way out. A missing or unreadable store means "no stored
claims", never an error and never an invented claim.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path

from atlas.privacy import contains_private_marker
from atlas.schemas import Claim, SourceCoverage, SourceStatus


@lru_cache(maxsize=4)
def _load(path: str, mtime_ns: int) -> dict[str, Claim]:  # mtime is part of the key, so edits reload
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT json FROM claims ORDER BY claim_id").fetchall()
    finally:
        conn.close()
    out: dict[str, Claim] = {}
    for (raw,) in rows:
        if contains_private_marker(raw):
            continue  # defence in depth: a private-case marker is never served from the public store
        try:
            c = Claim.model_validate_json(raw)
        except ValueError:  # one stale or invalid row must not take every endpoint down
            continue
        out[c.claim_id] = c
    return out


def load_claims(path: Path, *, hide_predicates: frozenset[str] = frozenset()) -> dict[str, Claim]:
    """Stored claims, minus any predicates the owner chose to hide from display."""
    try:
        claims = _load(str(path), path.stat().st_mtime_ns)
    except (OSError, sqlite3.Error):
        return {}
    if not hide_predicates:
        return claims
    return {i: c for i, c in claims.items() if c.predicate not in hide_predicates}


def paper_coverage(store_dir: Path) -> SourceCoverage | None:
    """One manifest row for the paper claims, from the recorded ingest log (never from generated text).

    `fetched` = statements the model proposed from ingested papers, `screened` = claims that passed every
    check. Papers that failed or were skipped are named in `error` so the gap is visible. None when there
    is no log: then no paper claims are claimed as coverage.
    """
    log = store_dir / "ingest_log.jsonl"
    if not log.exists():
        return None
    last: dict[str, dict] = {}
    for line in log.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue  # a partial line from a writer in progress
        if "source_id" in row:
            last[row["source_id"]] = row  # the latest outcome per paper
    ok = [r for r in last.values() if r.get("status") == "ingested"]
    bad = [r for r in last.values() if r.get("status") in {"failed", "skipped"}]
    if not last:
        return None
    stored = sum(r["claims_added"] + r["claims_already_present"] for r in ok)
    fetched = stored + sum(r["statements_quarantined"] for r in ok)
    note = f"{len(ok)} papers read, {len(bad)} not read (failed or skipped)" if bad else f"{len(ok)} papers read"
    return SourceCoverage(
        source="Paper claims (Europe PMC / PubMed)", status=SourceStatus.ok if ok else SourceStatus.failed,
        fetched=fetched if ok else None, screened=stored if ok else None, error=note,
    )
