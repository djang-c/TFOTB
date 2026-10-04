"""How a looked-up term (see atlas.terms) appears through the entity endpoints.

A term entry is a catalogue entry plus the papers found for it. It has no claims, so connections, routes and
the graph are empty and the gap says plainly that nothing has been read from papers yet.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.terms import TermStore

TERM_PREFIXES = ("MESH:", "TERM:")

NOTE = ("Added by a visitor's lookup and verified against public sources (NLM MeSH and Europe PMC). It is a catalogue "
        "entry with papers to read, not evidence: no claim about it has been extracted from a paper yet. Unreviewed by any expert.")


def is_term_id(entity_id: str) -> bool:
    return entity_id.startswith(TERM_PREFIXES)


def entity_of(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "type": row["type"] or "term", "label": row["label"], "identity_status": "resolved",
        "candidate_ids": [], "synonyms": row.get("synonyms", []), "xrefs": [],
        "attributes": {k: v for k, v in {"kind": row.get("kind"), "verified by": row.get("verified_by"),
                                         "MeSH": row.get("mesh_id"), "added": row.get("added_at", "")[:10]}.items() if v},
        "source_url": row["source_url"], "source_type": "database_record", "source_version": None,
        "retrieved_at": row.get("added_at", ""), "review_state": "unreviewed",
    }


def hit_of(row: dict[str, Any], query: str) -> dict[str, Any]:
    exact = query.strip().casefold() in [row["label"].casefold(), *(s.casefold() for s in row.get("synonyms", []))]
    return {"id": row["id"], "label": row["label"], "type": row["type"] or "term", "synonyms": row.get("synonyms", []),
            "matched": None, "match": "label" if exact else "all words", "source_type": "database_record", "added_by_lookup": True}


def summary_of(row: dict[str, Any]) -> list[dict[str, Any]]:
    out = [{"text": f"{row['label']} is recorded as a {row.get('kind') or 'medical term'}. {row.get('reason', '')}".strip(),
            "claim_ids": [], "source": "NLM MeSH" if row.get("verified_by") == "MeSH" else "Europe PMC"}]
    if row.get("scope_note"):
        out.append({"text": f"MeSH scope note: {row['scope_note']}", "claim_ids": [], "source": "NLM MeSH"})
    return out


def entity_view(row: dict[str, Any]) -> dict[str, Any]:
    return {"_synthetic": NOTE, "entity": entity_of(row), "claims": [], "claim_counts_by_predicate": {}, "reviewed_claims": 0,
            "summary": summary_of(row), "summary_method": "template", "papers": row.get("papers", []),
            "verification": {"by": row.get("verified_by"), "reason": row.get("reason"), "sources_checked": row.get("sources_checked", []),
                             "title_hits": row.get("title_hits")}}


def gap_view(row: dict[str, Any]) -> dict[str, Any]:
    checked = row.get("sources_checked") or []
    return {"_synthetic": NOTE, "gap": {
        "kind": "not_yet_researched",
        "statement": f"No claim about {row['label']} has been read from a paper yet. Missing is not the same as no connection.",
        "as_of": datetime.now(UTC).date().isoformat(), "known_claim_ids": [],
        "failed_sources": [c["source"] for c in checked if c.get("status") != "ok"],
        "missing_information": ["Claims read from full-text papers", "Links to genes, mechanisms and other diseases"],
        "reviewer_role": "A domain expert", "scope_note": NOTE,
    }, "coverage": {
        "manifest_id": f"LOOKUP:{row['id']}", "query": row["label"], "dataset_version": "lookup", "retrieved_at": row.get("added_at", ""),
        "per_source": [{"source": c["source"], "version": None, "status": c["status"],
                        "fetched": c.get("found") if isinstance(c.get("found"), int) else None, "screened": None, "error": None}
                       for c in checked],
        "per_channel": [], "generated_by": "atlas.terms",
    }}


def store_of(directory: Any) -> TermStore:
    return TermStore(directory)
