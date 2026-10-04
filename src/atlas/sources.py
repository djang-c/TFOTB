"""Source ingestion: PMID -> clean full text from Europe PMC (public, read-only API).

Why not PDFs: PDF text breaks words across lines ("ju-" / "venile"), keeps ligatures and drops
page headers into sentences, so correct quotes fail the verbatim check. Europe PMC serves the
publisher's full-text XML for open-access papers; paragraphs come out clean.

Only the article body and abstract are kept (no reference list), and bibliography markers
("CLN3 gene.5") are removed so the text reads as the authors wrote the sentence.
The licence Europe PMC reports is returned with the text; the caller must respect it
(e.g. CC BY-NC-ND text is cached locally for extraction only and never redistributed).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
Fetch = Callable[[str], bytes]


class SourceError(RuntimeError):
    """The paper was not found, is not open access, or has no full text. Nothing is guessed."""


@dataclass(frozen=True)
class FullText:
    pmid: str
    pmcid: str
    title: str
    license: str
    text: str
    url: str  # the API URL the text came from
    doi: str = ""
    journal: str = ""
    year: str = ""
    pub_types: tuple[str, ...] = ()

    @property
    def citation_url(self) -> str:
        """The link a reader can follow to the paper itself (DOI if the record has one)."""
        return f"https://doi.org/{self.doi}" if self.doi else f"https://europepmc.org/article/MED/{self.pmid}"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tfotb-fetch/1.0 (research; contact via repo)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _text(el: ET.Element) -> str:
    """Text of an element without bibliography markers; their tail text is kept."""
    out = [el.text or ""]
    for child in el:
        if not (child.tag == "xref" and child.get("ref-type") == "bibr"):
            out.append(_text(child))
        out.append(child.tail or "")
    return "".join(out)


_BLOCKS = {"p", "title", "article-title"}
# Contact, affiliation, funding and reference blocks are not scientific statements.
_SKIP = {"author-notes", "contrib-group", "aff", "funding-group", "permissions", "ref-list", "fn-group", "notes"}


def _walk(node: ET.Element, out: list[str]) -> None:
    for el in node:
        if el.tag in _SKIP:
            continue
        if el.tag in _BLOCKS:  # take the block once; do not descend (avoids duplicated nested text)
            t = " ".join(_text(el).split())
            if t:
                out.append(t)
        else:
            _walk(el, out)


def _paragraphs(root: ET.Element) -> list[str]:
    """Title, abstract and body paragraphs in reading order. The reference list is not read."""
    out: list[str] = []
    for path in (".//front/article-meta", ".//body"):
        node = root.find(path)
        if node is not None:
            _walk(node, out)
    return out


# Owner decision 2026-10-04: only credible published sources. A record must come from PubMed (so not a
# preprint), be a journal article in a named journal, and not be a retraction, editorial or similar.
# This checks the record's own metadata; peer review itself is not independently verified here.
_ARTICLE_TYPES = {"journal article", "research-article", "review-article", "review"}
_REJECT_TYPES = {
    "retracted publication", "retraction of publication", "preprint", "editorial", "comment", "letter",
    "news", "published erratum", "expression of concern", "withdrawn publication", "interview",
}


def credibility_problem(rec: dict) -> str | None:
    """Why a Europe PMC record is not an acceptable source, or None if it is."""
    if rec.get("source") != "MED":
        return f"not a PubMed-indexed article (source {rec.get('source')!r})"
    types = {t.lower() for t in (rec.get("pubTypeList") or {}).get("pubType", [])}
    bad = sorted(types & _REJECT_TYPES)
    if bad:
        return f"publication type excluded: {', '.join(bad)}"
    if not types & _ARTICLE_TYPES:
        return "not recorded as a journal article"
    if not (rec.get("journalInfo", {}).get("journal", {}).get("title") or "").strip():
        return "no journal recorded"
    return None


def fetch_full_text(pmid: str, fetch: Fetch = _get) -> FullText:
    """Open-access full text for a PMID, or SourceError. Never falls back to another source."""
    query = urllib.parse.quote(f"EXT_ID:{pmid} AND SRC:MED")
    found = json.loads(fetch(f"{API}/search?query={query}&format=json&resultType=core"))["resultList"]["result"]
    if not found:
        raise SourceError(f"PMID {pmid} not found in Europe PMC")
    rec = found[0]
    problem = credibility_problem(rec)
    if problem:
        raise SourceError(f"PMID {pmid} rejected as a source: {problem}")
    pmcid = rec.get("pmcid")
    if rec.get("isOpenAccess") != "Y" or not pmcid:
        raise SourceError(f"PMID {pmid} has no open-access full text in Europe PMC")
    url = f"{API}/{pmcid}/fullTextXML"
    root = ET.fromstring(fetch(url))
    paras = _paragraphs(root)
    if not paras:
        raise SourceError(f"{pmcid} XML contained no paragraphs")
    return FullText(
        pmid=pmid, pmcid=pmcid, title=rec.get("title", ""), license=rec.get("license", "UNKNOWN"),
        text="\n".join(paras), url=url, doi=rec.get("doi", ""),
        journal=rec["journalInfo"]["journal"]["title"], year=str(rec.get("pubYear", "")),
        pub_types=tuple((rec.get("pubTypeList") or {}).get("pubType", [])),
    )
