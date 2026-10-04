"""Find open-access papers about an entity automatically (Europe PMC search; public, read-only).

Search terms come from the entity's own ontology name plus any extra names in the policy, so a
researcher never has to hand over a keyword list. Discovery only proposes PMIDs; every paper still
goes through the same fetch, quote-verification and resolution checks before anything is stored.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass

from atlas.sources import API, Fetch, _get


@dataclass(frozen=True)
class Found:
    pmid: str
    title: str
    query: str


def build_query(term: str) -> str:
    term = term.replace('"', " ").strip()
    # Title or abstract only: a name buried in the full text would pull in unrelated papers.
    # Credible sources only: PubMed-indexed journal articles, never retractions or editorials. (The fetch
    # step re-checks each record's own metadata; this just avoids fetching what would be rejected.)
    return (
        f'(TITLE:"{term}" OR ABSTRACT:"{term}") AND OPEN_ACCESS:y AND SRC:MED AND PUB_TYPE:"Journal Article" '
        'NOT PUB_TYPE:"Retracted Publication" NOT PUB_TYPE:"Retraction of Publication" NOT PUB_TYPE:"Editorial" sort_date:y'
    )


class DiscoveryError(RuntimeError):
    """The literature search could not be completed (after retries). Nothing was guessed."""


def _fetch_with_retry(fetch: Fetch, url: str, attempts: int = 3, wait_s: float = 2.0) -> bytes:
    for n in range(1, attempts + 1):
        try:
            return fetch(url)
        except OSError as exc:  # timeouts and connection errors are usually momentary
            if n == attempts:
                raise DiscoveryError(f"literature search failed after {attempts} tries: {exc}") from exc
            time.sleep(wait_s * n)
    raise AssertionError("unreachable")


def discover(
    terms: Iterable[str], *, per_query: int = 10, fetch: Fetch = _get, wait_s: float = 2.0
) -> list[Found]:
    """Newest open-access PubMed papers per term, de-duplicated across terms, in term order."""
    seen: dict[str, Found] = {}
    for term in dict.fromkeys(t.strip() for t in terms if t and t.strip()):
        q = urllib.parse.quote(build_query(term))
        url = f"{API}/search?query={q}&format=json&resultType=lite&pageSize={per_query}"
        for rec in json.loads(_fetch_with_retry(fetch, url, wait_s=wait_s)).get("resultList", {}).get("result", []):
            pmid = rec.get("pmid")
            if pmid and pmid not in seen:
                seen[pmid] = Found(str(pmid), rec.get("title", ""), term)
    return list(seen.values())
