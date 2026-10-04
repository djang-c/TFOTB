"""Paper -> claims -> persistent store: the core of the weekly ingest job (docs/DATABRICKS.md).

One function, `ingest_papers`, so the same code runs from a local script today and from a scheduled
job later. Rules:
- Any open-access paper may be ingested (owner decision 2026-10-03: hackathon project, not commercial);
  the reported licence is recorded in the run log. A caller may still pass `allowed_licences` to
  restrict. A paper that is not open access, over the size cap, or beyond the per-run cap is SKIPPED
  and the reason is recorded; skipping is never silent and never a zero count.
- Calls go through the record/replay cache. Whether a live call may be made on a cache miss is the
  caller's explicit choice (`live`), so a scheduled run cannot spend money by accident.
- Stored claims are immutable. A claim ID that already exists with the same content is a no-op; the
  same ID with different content is quarantined, never overwritten.
- Every claim is stored `unreviewed` (the extraction layer guarantees it). Nothing is deleted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any
from xml.etree.ElementTree import ParseError

from atlas.db import AtlasDB
from atlas.extraction import SourceText, extract_claims
from atlas.llm.base import LLMClient, LLMError
from atlas.resolver import Resolver
from atlas.schemas import Claim, SourceCoverage, SourceStatus
from atlas.sources import FullText, SourceError, fetch_full_text


@dataclass
class PaperRun:
    source_id: str
    status: str  # "ingested" | "skipped" | "failed"
    reason: str = ""
    licence: str = ""
    claims_added: int = 0
    claims_already_present: int = 0
    statements_quarantined: int = 0
    prompt_version: str = ""
    from_cache: bool = False
    citation: str = ""  # the paper's DOI link or Europe PMC page, taken from its record
    journal: str = ""


@dataclass
class IngestReport:
    runs: list[PaperRun] = field(default_factory=list)

    def coverage(self) -> list[SourceCoverage]:
        """Per-source coverage for the manifest. Skipped and failed sources are shown as failed."""
        out = []
        for r in self.runs:
            if r.status == "ingested":
                passed = r.claims_added + r.claims_already_present
                out.append(
                    SourceCoverage(
                        source=r.source_id, version=r.prompt_version, status=SourceStatus.ok,
                        fetched=passed + r.statements_quarantined, screened=passed,
                    )
                )
            else:
                out.append(SourceCoverage(source=r.source_id, status=SourceStatus.failed, error=r.reason))
        return out


def _licence_allowed(licence: str, allowed: Iterable[str]) -> bool:
    return licence.strip().lower() in {a.strip().lower() for a in allowed}


def _store_claim(db: AtlasDB, claim: Claim, source_id: str) -> str:
    existing = db.get(Claim, claim.claim_id)
    if existing is None:
        db.put(claim)
        return "added"
    if existing == claim:
        return "already"
    db.quarantine(
        {"source_id": source_id, "claim_id": claim.claim_id},
        "claim_id exists with different content; not overwritten",
    )
    return "conflict"


def ingest_papers(
    pmids: Iterable[str],
    *,
    client: LLMClient,
    resolver: Resolver,
    db: AtlasDB,
    allowed_licences: Iterable[str] | None = None,  # None = any licence
    max_papers: int = 5,
    max_chars: int = 70_000,
    skip: Iterable[str] = (),
    fetch: Callable[[str], FullText] = fetch_full_text,
) -> IngestReport:
    """Ingest up to `max_papers` papers. `skip` holds source IDs already done in earlier runs."""
    report = IngestReport()
    done = set(skip)
    allowed = None if allowed_licences is None else tuple(allowed_licences)
    attempted = 0
    for pmid in dict.fromkeys(str(p).strip() for p in pmids if str(p).strip()):
        sid = f"PMID:{pmid}"
        if sid in done:
            continue
        if attempted >= max_papers:
            report.runs.append(PaperRun(sid, "skipped", f"per-run cap of {max_papers} papers reached"))
            continue
        attempted += 1
        try:
            ft = fetch(pmid)
        except (SourceError, OSError, ValueError, ParseError) as exc:
            # A network timeout, a malformed response or an unreadable XML body fails this paper only.
            report.runs.append(PaperRun(sid, "failed", f"{type(exc).__name__}: {exc}"[:300]))
            continue
        if allowed is not None and not _licence_allowed(ft.license, allowed):
            report.runs.append(
                PaperRun(sid, "skipped", f"licence {ft.license!r} is not on the allow-list", ft.license)
            )
            continue
        if len(ft.text) > max_chars:
            report.runs.append(
                PaperRun(sid, "skipped", f"text is {len(ft.text)} chars, over the {max_chars} cap", ft.license)
            )
            continue
        try:
            ex = extract_claims(client, SourceText(sid, ft.citation_url, ft.text), resolver)
        except LLMError as exc:  # e.g. replay-only run and no recorded response for this paper
            report.runs.append(PaperRun(sid, "failed", f"model call not made or failed: {exc}"[:300], ft.license))
            continue
        if ex.status != "extracted":
            report.runs.append(PaperRun(sid, "failed", ex.reason, ft.license))
            continue
        counts: dict[str, int] = {"added": 0, "already": 0, "conflict": 0}
        for claim in ex.claims:
            counts[_store_claim(db, claim, sid)] += 1
        for rejected in ex.quarantined:
            db.quarantine({"source_id": sid, "statement": rejected["statement"]}, rejected["reason"])
        report.runs.append(
            PaperRun(
                sid, "ingested", "", ft.license, counts["added"], counts["already"],
                len(ex.quarantined) + counts["conflict"], ex.prompt_version, ex.from_cache,
                ft.citation_url, ft.journal,
            )
        )
    return report


def ledger_rows(report: IngestReport) -> list[dict[str, Any]]:
    """Plain dicts for an append-only run log (one JSON line each)."""
    return [r.__dict__.copy() for r in report.runs]
