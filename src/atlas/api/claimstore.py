"""Read-only access to the persistent claim store (data/store/atlas.db, written by scripts/ingest_papers.py).

The API never writes here. The file is opened read-only, so a request cannot change the evidence, and
rows are re-validated as `Claim` on the way out. A missing or unreadable store means "no stored
claims", never an error and never an invented claim.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from atlas.schemas import Claim


@lru_cache(maxsize=4)
def _load(path: str, mtime_ns: int) -> dict[str, Claim]:  # mtime is part of the key, so edits reload
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT json FROM claims ORDER BY claim_id").fetchall()
    finally:
        conn.close()
    claims = (Claim.model_validate_json(r[0]) for r in rows)
    return {c.claim_id: c for c in claims}


def load_claims(path: Path, *, hide_predicates: frozenset[str] = frozenset()) -> dict[str, Claim]:
    """Stored claims, minus any predicates the owner chose to hide from display."""
    try:
        claims = _load(str(path), path.stat().st_mtime_ns)
    except (OSError, sqlite3.Error):
        return {}
    if not hide_predicates:
        return claims
    return {i: c for i, c in claims.items() if c.predicate not in hide_predicates}
