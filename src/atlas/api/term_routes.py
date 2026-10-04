"""POST /api/lookup: what to do with a search the catalogue could not answer.

The caller sends the text the visitor searched for. The server cleans it (anything that looks like a personal
identifier is refused and never sent anywhere), checks the catalogue and the term store, and only then asks the
public vocabularies (NLM MeSH, Europe PMC) whether it is a real medical term. A verified term is added to the
shared term store; anything else is reported as not verified, and the client keeps it on the visitor's own
device. No model is called and nothing is spent. The endpoint is rate limited because it writes.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from atlas.api.routes import _index
from atlas.api.termviews import NOTE, hit_of
from atlas.terms import TermRejected, TermStore, Verdict, clean_term, verify_term

router = APIRouter()

PER_CLIENT_PER_HOUR = 12
GLOBAL_PER_HOUR = 60


class LookupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(max_length=300)


class LookupLimiter:
    def __init__(self, per_client: int = PER_CLIENT_PER_HOUR, total: int = GLOBAL_PER_HOUR) -> None:
        self.per_client, self.total = per_client, total
        self._clients: dict[str, deque[float]] = defaultdict(deque)
        self._all: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            for q in (self._all, self._clients[client]):
                while q and now - q[0] > 3600:
                    q.popleft()
            if len(self._all) >= self.total or len(self._clients[client]) >= self.per_client:
                return False
            self._all.append(now)
            self._clients[client].append(now)
            return True


def terms(request: Request) -> TermStore:
    return request.app.state.terms


@router.get("/terms")
def term_list(request: Request) -> dict[str, Any]:
    rows = terms(request).all()
    return {"_synthetic": NOTE, "total": len(rows),
            "items": [{"id": r["id"], "label": r["label"], "type": r["type"], "kind": r.get("kind"), "added_at": r.get("added_at")}
                      for r in rows[-50:][::-1]]}


@router.post("/lookup")
def lookup(request: Request, body: LookupBody) -> dict[str, Any]:
    try:
        term = clean_term(body.query)
    except TermRejected as exc:
        return {"status": "rejected", "query": "", "reason": str(exc), "stored": False}

    # 1. Already known: the pinned ontologies, or a term added earlier.
    ix = _index(request)
    known = ix.search(term)["results"] if ix is not None else []
    added = [hit_of(r, term) for r in terms(request).find(term, limit=5)]
    if known or added:
        return {"status": "known", "query": term, "results": (known + added)[:10], "stored": False,
                "reason": "The catalogue already has an entry for this."}

    # 2. Ask the public vocabularies, within a rate limit (this endpoint can write).
    client = request.client.host if request.client else "unknown"
    if not request.app.state.lookup_limiter.allow(client):
        raise HTTPException(status_code=429, detail="Too many lookups just now. Try again later.")
    verify = request.app.state.term_verifier or verify_term
    verdict: Verdict = verify(term)
    base = {"query": term, "reason": verdict.reason, "sources_checked": verdict.sources_checked}
    if verdict.status != "verified":
        return {**base, "status": verdict.status, "stored": False, "label": verdict.label}

    try:
        row, persisted = terms(request).add(verdict, asked=term)
    except OverflowError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    return {**base, "status": "added", "stored": True, "persisted": persisted, "entity_id": row["id"], "label": row["label"],
            "kind": row.get("kind"), "verified_by": row.get("verified_by"), "papers": row.get("papers", []),
            "note": NOTE + ("" if persisted else " This server is read-only, so the entry lasts only until it restarts.")}
