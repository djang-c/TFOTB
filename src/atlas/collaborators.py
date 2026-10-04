"""Who studies this? Investigators and network overlap, from the papers behind the stored claims.

Brief, Module 3.3: surface when two "unrelated" disease communities already share a researcher. This builds
it from what we actually hold: the authors listed on each paper whose claims we stored. Rules:
- Authors are exactly as the paper's record lists them. We do not look anyone up or infer a role.
- An ORCID match is a strong match. Without an ORCID the match is by name only, and the output says so:
  records give "Chen J", so two different people can look identical.
- Authorship is not endorsement, availability or a contact route. The view says who published, not who to
  email; a verified contact is still needed before any outreach.
- Ordering is by how many of the person's papers are about OTHER diseases, then how many other diseases their
  papers touch, then paper count, then name. It is a practical
  ordering for finding bridges, not a measure of expertise or of biological relevance.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from atlas.schemas import Claim

NOTE = (
    "Authors are listed as the paper records give them. A match by name alone can join two different people; "
    "an ORCID match is stronger. Having published a paper does not mean a person is available, interested or "
    "the right contact. Nothing here is a verified contact route."
)
MAX_ITEMS = 15


def load_papers(store_dir: Path) -> dict[str, dict[str, Any]]:
    """Paper metadata by source ID ("PMID:123"), from the sidecar written during ingest. Latest row wins."""
    path = store_dir / "papers.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if "source_id" in row:
            out[row["source_id"]] = row
    return out


def _source_of(claim: Claim) -> str | None:
    m = re.fullmatch(r"STUDY:PMID-(\d+)", claim.lineage_id)
    return f"PMID:{m.group(1)}" if m else None


def _person_key(author: dict[str, Any]) -> tuple[str, str]:
    if author.get("orcid"):
        return ("orcid", author["orcid"])
    return ("name", re.sub(r"[^a-z ]", "", author["name"].casefold()).strip())


def collaborators_for(
    entity_id: str, claims: dict[str, Claim], papers: dict[str, dict[str, Any]], *, label_of=lambda _i: "",
) -> dict[str, Any]:
    """Investigators on papers whose stored claims name `entity_id`, with the other entities their papers cover."""
    by_source: dict[str, list[Claim]] = defaultdict(list)
    for c in claims.values():
        src = _source_of(c)
        if src and src in papers:
            by_source[src].append(c)

    def entities_of(cs: list[Claim]) -> set[str]:
        return {e for c in cs for e in (c.subject_id, c.object_id) if e.startswith("MONDO:")}

    people: dict[tuple[str, str], dict[str, Any]] = {}
    for src, cs in by_source.items():
        for a in papers[src].get("authors", []):
            p = people.setdefault(
                _person_key(a),
                {"name": a["name"], "orcid": a.get("orcid"), "affiliation": a.get("affiliation"), "sources": {}},
            )
            if a.get("orcid") and not p["orcid"]:
                p["orcid"] = a["orcid"]
            p["sources"][src] = cs
    items = []
    for p in people.values():
        mine = {s: cs for s, cs in p["sources"].items() if any(entity_id in (c.subject_id, c.object_id) for c in cs)}
        if not mine:
            continue
        others: dict[str, list[str]] = defaultdict(list)
        for cs in p["sources"].values():
            for d in entities_of(cs) - {entity_id}:
                others[d] += [c.claim_id for c in cs if d in (c.subject_id, c.object_id)]
        items.append({
            "name": p["name"], "orcid": p["orcid"], "affiliation": p["affiliation"],
            "match": "ORCID" if p["orcid"] else "name only (unverified)",
            # papers of this person about OTHER diseases that do not name this one: the clearest sign of a bridge
            "other_papers": len(set(p["sources"]) - set(mine)),
            "papers": [
                {k: papers[s].get(k) for k in ("source_id", "title", "journal", "year", "citation")}
                | {"claim_ids": sorted(c.claim_id for c in cs if entity_id in (c.subject_id, c.object_id))}
                for s, cs in sorted(mine.items())
            ],
            "also_studies": [
                {"entity_id": d, "label": label_of(d) or d, "claim_ids": sorted(set(ids))}
                for d, ids in sorted(others.items())
            ],
        })
    items.sort(key=lambda i: (-i["other_papers"], -len(i["also_studies"]), -len(i["papers"]), i["name"].casefold()))
    return {
        "items": items[:MAX_ITEMS], "total": len(items), "papers_considered": len(by_source), "note": NOTE,
        "bridges": sum(1 for i in items if i["also_studies"]),
    }
