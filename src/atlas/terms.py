"""Terms people look up that the catalogue has never seen: verify them against public sources, then record them.

A visitor may search for a disease, symptom or other medical term that is not in the pinned ontologies.
Two public sources decide whether it is a real medical term, with no model involved and nothing guessed:

1. NLM MeSH (through NCBI E-utilities): the term (or an entry term of a heading) is a MeSH heading in a
   medical branch of the tree (anatomy, organisms, diseases and symptoms, chemicals and drugs, procedures,
   mental health, biological processes). Headings in non-medical branches (information science, geography,
   humanities, ...) are refused.
2. Europe PMC: the term is a condition name (it contains a condition word such as "syndrome" or "disease")
   and appears in the TITLES of at least `MIN_TITLE_PAPERS` PubMed-indexed journal articles that are not
   retractions or editorials. Such a term is recorded as "found in the literature, not in MeSH": it may be a
   new or informal name.

A verified term is added to the shared term store with the papers that were found (each citation is taken
from the paper's own Europe PMC record). A term that fails verification is never stored here; the caller
keeps it locally for the user only. Nothing a visitor types is sent anywhere unless it passes `clean_term`,
which refuses anything that looks like a personal identifier.

This module reads claims from nothing and creates no claim: a term entry is a catalogue entry plus papers
to read, never evidence. Claims about it appear only when the paper pipeline extracts and verifies them.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.privacy import contains_private_marker
from atlas.sources import API, Fetch, _get

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MIN_TITLE_PAPERS = 2
MAX_TERMS_STORED = 5000
MAX_PAPERS = 5
MAX_SYNONYMS = 12

# First letter of a MeSH tree number -> what the heading is. Branches not listed are not medical terms.
MEDICAL_BRANCHES = {
    "A": "anatomy",
    "B": "organism",
    "C": "condition",
    "D": "chemical or drug",
    "E": "procedure",
    "F": "mental health",
    "G": "biological process",
}
_SYMPTOM_TREE = "C23.888"  # "Signs and Symptoms"
_NOT_MEDICAL_G = ("G17",)  # "Mathematical Concepts" sits in the G branch but is not biology (it holds "Machine Learning")

# Entity types the explorer already knows how to show.
_TYPE_OF_KIND = {"condition": "disease", "symptom": "phenotype", "chemical or drug": "drug", "biological process": "mechanism"}

# A name that reads as a medical condition. Used only for the literature route, where MeSH has no entry.
_CONDITION_WORD = re.compile(
    r"(syndrome|disease|disorder|deficien|dystroph|atroph|ataxi|dysplasi|myopath|neuropath|encephalopath|"
    r"cardiomyopath|leukodystroph|lipofuscinos|mucopolysaccharidos|glycogenos|acidemi|aciduri|osis\b|itis\b|"
    r"emia\b|penia\b|plasia\b|algia\b|oma\b|paresis|plegia|palsy|epilep|seizure|anomal|malformation|"
    r"cancer|tumou?r|carcinoma|lymphoma|leukemia|infection|fever|cyst|fibrosis|sclerosis|hypotonia)",
    re.IGNORECASE,
)

_INVISIBLE = dict.fromkeys([*range(0x20), 0x7F, *range(0x200B, 0x2010), 0x2060, 0xFEFF, 0xAD], None)
_EMAIL = re.compile(r"\S+@\S+")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_LONG_DIGITS = re.compile(r"\d[\d\s().-]{5,}\d")
_DATE = re.compile(r"\b\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}\b")
_IDENTIFIER_WORDS = re.compile(r"\b(mrn|dob|ssn|passport|insurance|medical record|date of birth)\b", re.IGNORECASE)


class TermRejected(ValueError):
    """The text looks like a personal identifier or is not a term at all; it is neither checked nor stored."""


def clean_term(text: str) -> str:
    """The term, tidied, or `TermRejected` with a reason that is safe to show."""
    t = unicodedata.normalize("NFKC", text or "")
    t = " ".join(t.split()).translate(_INVISIBLE)  # whitespace first, so tabs and newlines become spaces
    if len(t) < 2 or not re.search(r"[^\W\d_]", t):
        raise TermRejected("Type at least a couple of letters.")
    if len(t) > 80 or len(t.split()) > 8:
        raise TermRejected("That is too long for a term. Use the name of the disease, symptom or mechanism.")
    if (
        _EMAIL.search(t) or _URL.search(t) or _LONG_DIGITS.search(t) or _DATE.search(t)
        or _IDENTIFIER_WORDS.search(t) or contains_private_marker(t)
    ):
        raise TermRejected(
            "That looks like it may contain personal or identifying information, so it was not looked up. "
            "Enter only the name of a condition, symptom, gene or mechanism."
        )
    return t


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def slug(text: str) -> str:
    return re.sub(r"\s+", "-", norm(text))[:60] or "term"


@dataclass(frozen=True)
class Paper:
    pmid: str
    title: str
    journal: str
    year: str
    doi: str | None
    url: str

    def as_dict(self) -> dict[str, Any]:
        return {"pmid": self.pmid, "title": self.title, "journal": self.journal, "year": self.year,
                "doi": self.doi, "url": self.url}


@dataclass
class Verdict:
    term: str
    status: str  # verified | not_verified | not_medical | unavailable
    reason: str
    id: str | None = None
    label: str | None = None
    kind: str | None = None
    type: str | None = None
    method: str | None = None  # "MeSH" | "literature"
    mesh_id: str | None = None
    tree_numbers: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    scope_note: str | None = None
    papers: list[Paper] = field(default_factory=list)
    title_hits: int | None = None
    sources_checked: list[dict[str, Any]] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------- MeSH

def _eutils(path: str, params: dict[str, str], fetch: Fetch, wait_s: float) -> dict[str, Any]:
    key = os.environ.get("NCBI_API_KEY", "").strip()
    q = {**params, "retmode": "json", **({"api_key": key} if key else {})}
    url = f"{EUTILS}/{path}?{urllib.parse.urlencode(q)}"
    last: Exception | None = None
    for n in range(1, 5):  # NCBI allows about 3 requests per second without a key and answers 429 beyond that
        try:
            return json.loads(fetch(url))
        except (OSError, ValueError) as exc:
            last = exc
            if n < 4:
                time.sleep(wait_s * n)
    raise OSError(f"NCBI E-utilities did not answer: {last}")


def mesh_lookup(term: str, *, fetch: Fetch = _get, wait_s: float = 1.0) -> dict[str, Any] | None:
    """The MeSH record whose heading or entry term is exactly `term`, or None."""
    found = _eutils("esearch.fcgi", {"db": "mesh", "term": f'"{term}"[MeSH Terms]'}, fetch, wait_s)
    ids = (found.get("esearchresult") or {}).get("idlist") or []
    if not ids:
        return None
    time.sleep(wait_s / 3)
    summary = _eutils("esummary.fcgi", {"db": "mesh", "id": ids[0]}, fetch, wait_s)
    rec = (summary.get("result") or {}).get(ids[0])
    return rec if isinstance(rec, dict) else None


def classify_mesh(rec: dict[str, Any]) -> tuple[str | None, list[str]]:
    """(kind, tree numbers) for a MeSH record; kind None when no branch is a medical one."""
    trees = [x["treenum"] for x in rec.get("ds_idxlinks") or [] if isinstance(x, dict) and x.get("treenum")]
    if not trees:
        # A supplementary concept record (a rare disease, chemical or protocol) has no tree numbers of its own.
        return ("supplementary concept", []) if str(rec.get("ds_meshui", "")).startswith("C") else (None, [])
    kinds = []
    for t in trees:
        if t.startswith(_SYMPTOM_TREE):
            kinds.append("symptom")
        elif t[:1] in MEDICAL_BRANCHES and not t.startswith(_NOT_MEDICAL_G):
            kinds.append(MEDICAL_BRANCHES[t[:1]])
    if not kinds:
        return None, trees
    return ("symptom" if "symptom" in kinds else kinds[0]), trees


# ------------------------------------------------------------------------------------------ Europe PMC

def _epmc(query: str, size: int, fetch: Fetch, wait_s: float, sort: str = "") -> dict[str, Any]:
    url = f"{API}/search?query={urllib.parse.quote(query + sort)}&format=json&resultType=lite&pageSize={size}"
    last: Exception | None = None
    for n in range(1, 4):
        try:
            return json.loads(fetch(url))
        except (OSError, ValueError) as exc:
            last = exc
            if n < 3:
                time.sleep(wait_s * n)
    raise OSError(f"Europe PMC did not answer: {last}")


_JOURNAL_ONLY = ('SRC:MED AND PUB_TYPE:"Journal Article" NOT PUB_TYPE:"Retracted Publication" '
                 'NOT PUB_TYPE:"Retraction of Publication" NOT PUB_TYPE:"Editorial"')


def _paper(rec: dict[str, Any]) -> Paper | None:
    pmid, title = str(rec.get("pmid") or ""), (rec.get("title") or "").strip()
    if not pmid or not title:
        return None
    doi = (rec.get("doi") or "").strip() or None
    return Paper(pmid, title.rstrip("."), (rec.get("journalTitle") or "").strip(), str(rec.get("pubYear") or ""), doi,
                 f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")


def papers_about(term: str, *, fetch: Fetch = _get, wait_s: float = 1.0, title_only: bool = False) -> tuple[int, list[Paper]]:
    """(hit count, up to MAX_PAPERS papers) of PubMed-indexed journal articles naming the term."""
    t = term.replace('"', " ").strip()
    where = f'TITLE:"{t}"' if title_only else f'(TITLE:"{t}" OR ABSTRACT:"{t}")'
    data = _epmc(f"{where} AND {_JOURNAL_ONLY}", MAX_PAPERS, fetch, wait_s, sort=" sort_date:y")
    papers = [p for p in map(_paper, (data.get("resultList") or {}).get("result") or []) if p]
    return int(data.get("hitCount") or 0), papers


# --------------------------------------------------------------------------------------------- verdict

def verify_term(term: str, *, fetch: Fetch = _get, wait_s: float = 1.0) -> Verdict:
    """Decide whether `term` is a verifiable medical term. Never raises for network trouble: that is `unavailable`."""
    checked: list[dict[str, Any]] = []
    try:
        rec = mesh_lookup(term, fetch=fetch, wait_s=wait_s)
        checked.append({"source": "NLM MeSH", "status": "ok", "found": rec is not None})
    except OSError as exc:
        return Verdict(term, "unavailable", f"The public vocabulary service could not be reached ({exc}). Nothing was decided.",
                       sources_checked=[{"source": "NLM MeSH", "status": "failed", "found": None}])

    if rec is not None:
        kind, trees = classify_mesh(rec)
        names = [str(x) for x in rec.get("ds_meshterms") or []]
        heading = names[0] if names else term
        if kind is None:
            return Verdict(term, "not_medical", f"It is a MeSH heading ({heading}), but in a non-medical branch of the vocabulary.",
                           label=heading, tree_numbers=trees, sources_checked=checked)
        try:
            hits, papers = papers_about(heading, fetch=fetch, wait_s=wait_s)
            checked.append({"source": "Europe PMC", "status": "ok", "found": hits})
        except OSError:
            hits, papers = 0, []
            checked.append({"source": "Europe PMC", "status": "failed", "found": None})
        ui = str(rec.get("ds_meshui") or "")
        return Verdict(
            term, "verified", f"{heading} is a {kind} heading in NLM MeSH ({ui}).", id=f"MESH:{ui}", label=heading, kind=kind,
            type=_TYPE_OF_KIND.get(kind, "term"), method="MeSH", mesh_id=ui, tree_numbers=trees,
            synonyms=[n for n in dict.fromkeys(names[1:]) if norm(n) != norm(heading)][:MAX_SYNONYMS],
            scope_note=(rec.get("ds_scopenote") or None), papers=papers, title_hits=hits, sources_checked=checked,
        )

    # Not in MeSH: only a condition name that appears in several journal-article titles is accepted.
    if not _CONDITION_WORD.search(term):
        return Verdict(term, "not_verified", "It is not a MeSH heading and does not read as a condition name, so it could not be verified.",
                       sources_checked=checked)
    try:
        hits, papers = papers_about(term, fetch=fetch, wait_s=wait_s, title_only=True)
        checked.append({"source": "Europe PMC", "status": "ok", "found": hits})
    except OSError as exc:
        checked.append({"source": "Europe PMC", "status": "failed", "found": None})
        return Verdict(term, "unavailable", f"The literature service could not be reached ({exc}). Nothing was decided.",
                       sources_checked=checked)
    if hits < MIN_TITLE_PAPERS:
        return Verdict(term, "not_verified",
                       f"It is not a MeSH heading, and only {hits} PubMed-indexed journal article title(s) contain it "
                       f"(at least {MIN_TITLE_PAPERS} are needed).", title_hits=hits, sources_checked=checked)
    return Verdict(
        term, "verified",
        f"Not in MeSH, but {hits} PubMed-indexed journal articles name it in their titles. It may be a new or informal name; "
        "it is recorded as found in the literature, not as an established diagnosis.",
        id=f"TERM:{slug(term)}", label=term, kind="condition (found in the literature)", type="disease", method="literature",
        papers=papers, title_hits=hits, sources_checked=checked,
    )


# ------------------------------------------------------------------------------------------------ store

class TermStore:
    """Verified terms, one JSON line each (data/store/terms.jsonl). Append-only; the latest row per ID wins.

    If the file cannot be written (a read-only deployment) the term is kept in memory for this process and
    `add` reports `persisted=False`, so the caller can say so."""

    def __init__(self, directory: Path) -> None:
        self.path = directory / "terms.jsonl"
        self._lock = threading.Lock()
        self._memory: dict[str, dict[str, Any]] = {}

    def _read(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("id") and row.get("label"):
                    out[row["id"]] = row
        return {**out, **self._memory}

    def all(self) -> list[dict[str, Any]]:
        return list(self._read().values())

    def get(self, term_id: str) -> dict[str, Any] | None:
        return self._read().get(term_id)

    def find(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Exact name or synonym first, then names that start with or contain the query."""
        q = norm(query)
        if not q:
            return []
        ranked: list[tuple[int, dict[str, Any]]] = []
        for row in self._read().values():
            names = [norm(row["label"]), *(norm(s) for s in row.get("synonyms", []))]
            score = 0 if q in names else 1 if any(n.startswith(q) for n in names) else 2 if any(q in n for n in names) else 3
            if score < 3:
                ranked.append((score, row))
        return [r for _, r in sorted(ranked, key=lambda x: x[0])][:limit]

    def add(self, verdict: Verdict, *, asked: str) -> tuple[dict[str, Any], bool]:
        """Record a verified term (idempotent). Returns (record, persisted)."""
        if verdict.status != "verified" or not verdict.id or not verdict.label:
            raise ValueError("only a verified term can be added")
        with self._lock:
            have = self._read()
            if verdict.id in have:
                return have[verdict.id], True
            if len(have) >= MAX_TERMS_STORED:
                raise OverflowError("the term store is full")
            row = {
                "id": verdict.id, "label": verdict.label, "type": verdict.type, "kind": verdict.kind,
                "synonyms": verdict.synonyms, "verified_by": verdict.method, "mesh_id": verdict.mesh_id,
                "tree_numbers": verdict.tree_numbers, "scope_note": verdict.scope_note,
                "source_url": (f"https://meshb.nlm.nih.gov/record/ui?ui={verdict.mesh_id}" if verdict.mesh_id
                               else (verdict.papers[0].url if verdict.papers else "https://europepmc.org/")),
                "reason": verdict.reason, "title_hits": verdict.title_hits,
                "papers": [p.as_dict() for p in verdict.papers], "sources_checked": verdict.sources_checked,
                "asked_as": asked, "added_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "review_state": "unreviewed", "source_type": "database_record",
            }
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                persisted = True
            except OSError:
                self._memory[verdict.id] = row
                persisted = False
            return row, persisted


Verifier = Callable[[str], Verdict]
