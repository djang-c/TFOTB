"""One global search over the pinned ontologies: disease, gene or symptom, by any name.

Rules (PLAN; the brief's "one global search ... with clear synonym resolution"):
- Matching is lexical and explained: every hit says which label or synonym matched and how
  (identifier, label, exact or related synonym, every word present, or a close spelling).
  Close spellings are suggestions, never resolutions; a name shared by several entries is shown
  as ambiguous with every candidate (resolver rules, T03).
- Relevance orders the *matches* only. Related entries come from recorded data (HPO gene-disease
  file, HPO annotations, the phenotype channel) and carry the source they came from. No number
  here is a confidence.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from atlas.channels.base import ChannelRegistry
from atlas.channels.claims import build_claim_channels
from atlas.channels.phenotype import PhenotypeChannel
from atlas.connections import run_query
from atlas.resolver import (
    _TIER_NAME,
    DISEASE,
    ENTITY_TYPES,
    GENE,
    PHENOTYPE,
    TIER_LABEL,
    Resolver,
    normalize,
)
from atlas.schemas import SourceCoverage, SourceStatus
from atlas.store import PublicStore
from atlas.structured import gene_disease_claims

MATCH_ORDER = ("identifier", "label", "exact synonym", "related synonym", "all words", "starts with", "close spelling")
_TIER_MATCH = {0: "label", 1: "exact synonym", 2: "related synonym"}
RELATED_LIMIT = 12
CLOSE_SPELLING_MIN = 0.75  # every query word needs a name word at least this close
NON_HUMAN_ROOT = "MONDO:0005583"  # "non-human animal disease"; its subtree is left out of search
_PURL = "http://purl.obolibrary.org/obo/"


@dataclass(frozen=True)
class Hit:
    id: str
    type: str
    label: str
    matched: str
    match: str  # one of MATCH_ORDER

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "label": self.label, "matched": self.matched,
                "match": self.match, "source_type": "database_record"}


class SearchIndex:
    def __init__(self, resolver: Resolver, phenotype: PhenotypeChannel | None = None,
                 gene_disease: list[dict[str, str]] | None = None,
                 parents: dict[str, set[str]] | None = None) -> None:
        self.r, self.ph = resolver, phenotype
        self.parents = parents or {}
        self.excluded = {x for x in self.parents if NON_HUMAN_ROOT in self.ancestors(x)}
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE names USING fts5(norm, entity_id UNINDEXED, type UNINDEXED, "
                        "text UNINDEXED, tier UNINDEXED, tokenize='trigram')")
        rows = [
            (norm, eid, etype, text, tier)
            for etype in ENTITY_TYPES
            for norm, entries in resolver._index[etype].items()
            for eid, text, tier in entries
            if eid not in self.excluded
        ]
        self.db.executemany("INSERT INTO names VALUES (?,?,?,?,?)", rows)
        # Trigrams need 3 characters, so 1-2 character queries use a plain sorted prefix index.
        self.db.execute("CREATE TABLE prefix (norm TEXT, entity_id TEXT, type TEXT, text TEXT, tier INTEGER)")
        self.db.executemany("INSERT INTO prefix VALUES (?,?,?,?,?)", rows)
        self.db.execute("CREATE INDEX prefix_norm ON prefix (norm)")
        self.size = len(rows)
        self.names_of: dict[str, set[tuple[str, int]]] = {}
        for _norm, eid, _etype, text, tier in rows:
            if tier != TIER_LABEL:
                self.names_of.setdefault(eid, set()).add((text, tier))
        # gene <-> disease: HPO genes_to_disease rows become sourced claims (atlas.structured).
        claims, self.g2d_tally = gene_disease_claims(gene_disease or [], resolver, exclude=self.excluded)
        self.store = PublicStore()
        for c in claims:
            self.store.add(c)
        self.genes_of: dict[str, list[dict[str, str]]] = {}
        self.diseases_of: dict[str, list[dict[str, str]]] = {}
        for c in claims:
            link = {"association": c.context["association_type"], "source_id": c.context["via"],
                    "source": "HPO genes_to_disease", "claim_id": c.claim_id}
            if all(x["id"] != c.object_id for x in self.diseases_of.get(c.subject_id, [])):
                self.diseases_of.setdefault(c.subject_id, []).append({"id": c.object_id, **link})
            if all(x["id"] != c.subject_id for x in self.genes_of.get(c.object_id, [])):
                self.genes_of.setdefault(c.object_id, []).append({"id": c.subject_id, **link})
        self.registry = ChannelRegistry()
        if phenotype:
            self.registry.register(phenotype)
        for ch in build_claim_channels(self.store):
            if ch.channel_id == "dna_variants":
                self.registry.register(ch)

    @classmethod
    def from_raw(cls, raw_dir: Path) -> SearchIndex:
        raw = Path(raw_dir)
        r = Resolver.from_raw(raw)
        ph = PhenotypeChannel.from_raw(raw, r)
        with (raw / "hpo" / "genes_to_disease.txt").open(newline="") as f:
            g2d = list(csv.DictReader(f, delimiter="\t"))
        graph = json.loads((raw / "mondo" / "mondo.json").read_text())["graphs"][0]
        parents: dict[str, set[str]] = {}
        for e in graph["edges"]:
            if e["pred"] == "is_a" and e["sub"].startswith(_PURL + "MONDO_") and e["obj"].startswith(_PURL + "MONDO_"):
                parents.setdefault(_curie(e["sub"]), set()).add(_curie(e["obj"]))
        return cls(r, ph, g2d, parents)

    def ancestors(self, entity_id: str) -> set[str]:
        out: set[str] = set()
        stack = list(self.parents.get(entity_id, ()))
        while stack:
            p = stack.pop()
            if p not in out:
                out.add(p)
                stack.extend(self.parents.get(p, ()))
        return out

    # ---- matching ----
    def search(self, q: str, limit: int = 20) -> dict[str, Any]:
        q = q.strip()
        norm = normalize(q)
        if not norm:
            return {"query": q, "results": [], "ambiguous": False}
        best: dict[str, Hit] = {}

        def keep(h: Hit) -> None:
            old = best.get(h.id)
            if old is None or MATCH_ORDER.index(h.match) < MATCH_ORDER.index(old.match):
                best[h.id] = h

        for etype in ENTITY_TYPES:
            if ":" in q:
                res = self.r.resolve(q, etype)
                if res.status == "resolved":
                    keep(Hit(res.resolved_id, etype, self.r.label_of(res.resolved_id), q, "identifier"))
            for eid, text, tier in self.r._index[etype].get(norm, []):
                keep(Hit(eid, etype, self.r.label_of(eid), text, _TIER_MATCH[tier]))

        # Every word of the query appears in one name ("Niemann-Pick type C" -> "Niemann-Pick disease type C").
        words = norm.split()
        long_words = [w for w in words if len(w) >= 3]
        if long_words:
            match = " AND ".join(f'"{w}"' for w in long_words)
            cur = self.db.execute(
                "SELECT norm, entity_id, type, text, tier FROM names WHERE names MATCH ? "
                "ORDER BY length(norm) LIMIT 400", (match,))
            for name, eid, etype, text, _tier in cur:
                name_words = name.split()
                if all(any(nw.startswith(w) for nw in name_words) for w in words):
                    keep(Hit(eid, etype, self.r.label_of(eid), text, "all words"))

        if not long_words:
            for etype in ENTITY_TYPES:  # a few of each type, so short gene symbols do not crowd out the rest
                cur = self.db.execute(
                    "SELECT entity_id, type, text FROM prefix WHERE type = ? AND norm >= ? AND norm < ? "
                    "ORDER BY tier, length(norm), norm LIMIT 7", (etype, norm, norm + "\uffff"))
                for eid, et, text in cur:
                    keep(Hit(eid, et, self.r.label_of(eid), text, "starts with"))

        if len(best) < 3 and long_words:
            for etype in ENTITY_TYPES:
                res = self.r.resolve(q, etype)
                if res.status == "suggestions":
                    for c in res.candidates:
                        keep(Hit(c.id, etype, c.label, c.matched, "close spelling"))
            # Misspelled words the resolver's word index cannot see: gather names sharing a word
            # prefix, keep only close spellings of the whole query. Suggestions, never resolutions.
            pool: set[tuple[str, str, str, str]] = set()
            for w in long_words:
                pool.update(self.db.execute(
                    "SELECT norm, entity_id, type, text FROM names WHERE names MATCH ? LIMIT 5000", (f'"{w[:3]}"',)))
            scored = []
            for name, eid, etype, text in pool:
                closeness = _word_closeness(words, name.split())
                if closeness >= CLOSE_SPELLING_MIN:
                    scored.append((-closeness, len(name), eid, etype, text))
            for _c, _n, eid, etype, text in sorted(scored)[:8]:
                keep(Hit(eid, etype, self.r.label_of(eid), text, "close spelling"))

        for eid in [k for k in best if k in self.excluded]:
            del best[eid]
        type_rank = {t: i for i, t in enumerate((DISEASE, GENE, PHENOTYPE))}
        hits = sorted(best.values(), key=lambda h: (MATCH_ORDER.index(h.match), len(h.matched), type_rank.get(h.type, 9), h.label))
        # Resolver rule: a unique label wins; any other name used by more than one entry is ambiguous.
        named = [h for h in hits if h.match in ("label", "exact synonym", "related synonym")]
        labels = [h for h in named if h.match == "label"]
        ambiguous = len(named) > 1 and len(labels) != 1
        return {"query": q, "results": [h.as_dict() for h in hits[:limit]], "ambiguous": ambiguous}

    # ---- what connects to an entry ----
    def related(self, entity_id: str) -> dict[str, Any]:
        etype = next((t for t in ENTITY_TYPES if entity_id in self.r._labels[t]), None)
        if etype is None:
            return {"entity_id": entity_id, "groups": []}
        lab = self.r.label_of
        groups: list[dict[str, Any]] = []
        if etype == DISEASE:
            genes = self.genes_of.get(entity_id, [])
            if genes:
                groups.append({"kind": "genes", "title": "Genes linked to this disease",
                               "source": "HPO genes_to_disease (via OMIM / Orphanet cross-references)",
                               "total": len(genes),
                               "items": [{**g, "label": lab(g["id"]), "type": GENE} for g in genes[:RELATED_LIMIT]]})
            if self.ph:
                cands = [c for c in self.ph.retrieve_candidates(entity_id, {"max_candidates": RELATED_LIMIT * 2})
                         if c not in self.excluded][:RELATED_LIMIT]
                items = []
                for c in cands:
                    cmp = self.ph.compare(entity_id, c, {})
                    items.append({"id": c, "label": lab(c), "type": DISEASE, "score": cmp.score,
                                  "shared": cmp.context_matches[:3]})
                if items:
                    groups.append({"kind": "phenotype_neighbours", "title": "Diseases with a similar pattern of symptoms",
                                   "source": "Phenotype channel: shared specific HPO terms (listed by number shared); "
                                             "overlap is BMA-Lin similarity, not a probability",
                                   "total": len(items), "items": items})
        elif etype == GENE:
            ds = self.diseases_of.get(entity_id, [])
            if ds:
                groups.append({"kind": "diseases", "title": "Diseases linked to this gene",
                               "source": "HPO genes_to_disease (via OMIM / Orphanet cross-references)",
                               "total": len(ds),
                               "items": [{**d, "label": lab(d["id"]), "type": DISEASE} for d in ds[:RELATED_LIMIT]]})
        elif etype == PHENOTYPE and self.ph:
            ds = sorted(set(self.ph._by_term.get(entity_id, ())) - self.excluded, key=lambda m: (len(self.ph._terms.get(m, ())), m))
            if ds:
                groups.append({"kind": "diseases", "title": "Diseases annotated with this symptom",
                               "source": "HPO phenotype.hpoa (includes more specific forms of the symptom); "
                                         "listed with the most narrowly described diseases first",
                               "total": len(ds),
                               "items": [{"id": m, "label": lab(m), "type": DISEASE} for m in ds[:RELATED_LIMIT]]})
        return {"entity_id": entity_id, "type": etype, "label": lab(entity_id), "groups": groups}

    def connections(self, entity_id: str) -> dict[str, Any]:
        """Q1 for a real disease: the T09 engine over the phenotype channel and gene-level claims.
        Coverage counts are the rows this process loaded, recorded at load time."""
        if entity_id not in self.r._labels[DISEASE]:
            return {"results": [], "labels": {}, "coverage": None, "gap": None}
        versions = self.r.versions
        per_source = [
            SourceCoverage(source="HPO genes_to_disease", version=versions.get("hpo/genes_to_disease.txt"),
                           status=SourceStatus.ok, fetched=self.g2d_tally["rows"], screened=self.g2d_tally["claims"]),
        ]
        if self.ph:
            per_source.append(SourceCoverage(source="HPO phenotype.hpoa", version=versions.get("hpo/phenotype.hpoa"),
                                             status=SourceStatus.ok, fetched=self.ph.n_diseases,
                                             screened=self.ph.n_diseases - self.ph._unmapped))
        out = run_query(entity_id, self.registry, self.store.claims, dataset_version="pinned-ontologies",
                        per_source=per_source, source_versions=versions, context={"max_candidates": RELATED_LIMIT})
        results = [r.result.model_dump(mode="json") for r in out.ranked if r.result.candidate_id not in self.excluded]
        labels = {r["candidate_id"]: self.r.label_of(r["candidate_id"]) for r in results}
        for r in results:  # features named in channel matches ("shared HGNC:2074")
            for c in r["comparisons"]:
                for m in c["context_matches"]:
                    for tok in re.findall(r"\b(?:HGNC|MONDO|HP|GO):\d+", m):
                        labels.setdefault(tok, self.r.label_of(tok) or tok)
        return {"results": results, "labels": labels, "coverage": out.coverage.model_dump(mode="json"),
                "gap": out.gap.model_dump(mode="json") if out.gap else None}

    def claim(self, claim_id: str) -> dict[str, Any] | None:
        c = self.store.claims.get(claim_id)
        return c.model_dump(mode="json") if c else None

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        etype = next((t for t in ENTITY_TYPES if entity_id in self.r._labels[t]), None)
        if etype is None:
            return None
        names = sorted(self.names_of.get(entity_id, ()), key=lambda x: (x[1], x[0].lower()))
        return {"id": entity_id, "type": etype, "label": self.r.label_of(entity_id),
                "synonyms": [t for t, _ in names][:12],
                "synonym_kinds": {t: _TIER_NAME[k] for t, k in names[:12]},
                "source_type": "database_record", "version": self.r.versions}


def _curie(purl: str) -> str:
    return purl[len(_PURL):].replace("_", ":", 1)


def _word_closeness(query_words: list[str], name_words: list[str]) -> float:
    """The weakest query word's best match in the name (0 if any word has nothing close)."""
    if not name_words:
        return 0.0
    return min(max(SequenceMatcher(None, w, n).ratio() for n in name_words) for w in query_words)
