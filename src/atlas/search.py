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
import threading
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from atlas.cards import CardError, asset_reuse, evidence_brief
from atlas.channels.base import ChannelRegistry
from atlas.channels.claims import build_claim_channels
from atlas.channels.phenotype import PhenotypeChannel
from atlas.connections import run_query
from atlas.gard import GardSource
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
from atlas.schemas import AssetResult, Claim, SourceCoverage, SourceStatus
from atlas.store import PublicStore
from atlas.structured import gene_disease_claims
from atlas.trials import TrialsSource

MATCH_ORDER = ("identifier", "label", "exact synonym", "related synonym", "all words", "starts with", "close spelling")
_TIER_MATCH = {0: "label", 1: "exact synonym", 2: "related synonym"}
RELATED_LIMIT = 12
GENES_PER_DISEASE = 4  # in the graph only; e.g. MELAS lists 17 mitochondrial genes
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


_NEGATION = re.compile(r"^(?:no|not|without|absent|denies|never)\b\s*", re.IGNORECASE)


class SearchIndex:
    def __init__(self, resolver: Resolver, phenotype: PhenotypeChannel | None = None,
                 gene_disease: list[dict[str, str]] | None = None,
                 parents: dict[str, set[str]] | None = None) -> None:
        self.r, self.ph = resolver, phenotype
        self.parents = parents or {}
        self.excluded = {x for x in self.parents if NON_HUMAN_ROOT in self.ancestors(x)}
        self.children: dict[str, set[str]] = {}
        for child, ps in self.parents.items():
            if child not in self.excluded:
                for p in ps:
                    self.children.setdefault(p, set()).add(child)
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
        self.trials = TrialsSource()
        self.gard = GardSource()
        self.gard_of: dict[str, list[str]] = {}  # MONDO -> GARD IDs, from MONDO's own cross-references
        for xref, ids in resolver._xrefs.items():
            if xref.startswith("gard:"):
                for i in ids:
                    self.gard_of.setdefault(i, []).append("GARD:" + xref.split(":", 1)[1])
        self._outcomes: dict[str, Any] = {}  # T09 outcome per disease, reused by the action cards
        self._phenotype = phenotype
        self._lock = threading.Lock()
        self._paper_version: object = None
        self._paper_coverage: SourceCoverage | None = None
        self._rank_store = self.store  # the claims the ranking engine reads (HPO claims, plus paper claims if set)
        self.registry = self._build_registry(self.store)

    def _build_registry(self, store: PublicStore) -> ChannelRegistry:
        reg = ChannelRegistry()
        if self._phenotype:
            reg.register(self._phenotype)
        for ch in build_claim_channels(store):  # all four claim channels read the same combined store
            reg.register(ch)
        return reg

    def set_paper_claims(self, claims: dict[str, Claim], version: object, coverage: SourceCoverage | None = None) -> None:
        """Make claims read from papers part of the ranking, not only of the graph.

        The ranking then sees the HPO claims AND the paper claims, so a disease pair that shares a paper-reported
        feature can reach "literature-supported lead". Cheap when `version` (the store file's mtime) is unchanged;
        when it changes, cached connection results are dropped so they are never served stale.
        """
        with self._lock:
            if version == self._paper_version:
                return
            store = PublicStore()
            for c in self.store.claims.values():
                store.add(c)
            for c in claims.values():
                store.add(c)
            self._rank_store, self._paper_version, self._paper_coverage = store, version, coverage
            self.registry = self._build_registry(store)
            self._outcomes.clear()

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
            elif self.subtype_genes(entity_id):
                sub = self.subtype_genes(entity_id)
                groups.append({"kind": "subtype_genes", "title": "Genes recorded on more specific forms of this disease",
                               "source": "HPO genes_to_disease (on the subtypes shown) + MONDO hierarchy",
                               "total": len(sub),
                               "items": [{**g, "label": lab(g["id"]), "type": GENE,
                                          "association": g["association"], "source_id": f"{g['source_id']}, on {lab(g['via'])}"}
                                         for g in sub[:RELATED_LIMIT]]})
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
            return {"results": [], "labels": {}, "hierarchy": {}, "coverage": None, "gap": None}
        versions = self.r.versions
        per_source = [
            SourceCoverage(source="HPO genes_to_disease", version=versions.get("hpo/genes_to_disease.txt"),
                           status=SourceStatus.ok, fetched=self.g2d_tally["rows"], screened=self.g2d_tally["claims"]),
        ]
        if self.ph:
            per_source.append(SourceCoverage(source="HPO phenotype.hpoa", version=versions.get("hpo/phenotype.hpoa"),
                                             status=SourceStatus.ok, fetched=self.ph.n_diseases,
                                             screened=self.ph.n_diseases - self.ph._unmapped))
        if self._paper_coverage is not None:
            per_source.append(self._paper_coverage)
        out = self._outcomes.get(entity_id)
        if out is None:
            out = run_query(entity_id, self.registry, self._rank_store.claims, dataset_version="pinned-ontologies",
                            per_source=per_source, source_versions=versions, context={"max_candidates": RELATED_LIMIT})
            self._outcomes[entity_id] = out
        results = [r.result.model_dump(mode="json") for r in out.ranked if r.result.candidate_id not in self.excluded]
        labels = {r["candidate_id"]: self.r.label_of(r["candidate_id"]) for r in results}
        hierarchy = {r["candidate_id"]: n for r in results if (n := self.hierarchy_note(entity_id, r["candidate_id"]))}
        for r in results:  # features named in channel matches ("shared HGNC:2074")
            for c in r["comparisons"]:
                for m in c["context_matches"]:
                    for tok in re.findall(r"\b(?:HGNC|MONDO|HP|GO):\d+", m):
                        labels.setdefault(tok, self.r.label_of(tok) or tok)
        return {"results": results, "labels": labels, "hierarchy": hierarchy,
                "coverage": out.coverage.model_dump(mode="json"),
                "gap": out.gap.model_dump(mode="json") if out.gap else None}

    def assets(self, entity_id: str) -> dict[str, Any]:
        """Q2 for a real disease: studies on ClinicalTrials.gov that list this disease by name."""
        if entity_id not in self.r._labels[DISEASE]:
            return {"assets": [], "coverage": None}
        syn = self.names_of.get(entity_id, ())
        names = {t for t, _tier in syn}
        label = self.r.label_of(entity_id)
        exact = sorted({t for t, tier in syn if tier == 1 and len(t) > 3 and not t.isupper()}, key=len)[:6]
        return self.trials.for_disease(entity_id, label, names, [label, *exact])

    def graph(self, entity_id: str, max_nodes: int = 40) -> dict[str, Any]:
        """Two steps around an entry. Gene links are claims (clickable evidence). Symptom-similarity
        links are computed by the phenotype channel, not claims: they carry `claim_id: None`, the
        similarity, and status `computational_prediction`, so the UI can never present them as sourced."""
        etype = next((t for t in ENTITY_TYPES if entity_id in self.r._labels[t]), None)
        if etype not in (DISEASE, GENE):
            return {"nodes": [], "edges": [], "truncated": False, "omitted": 0}
        nodes: dict[str, str] = {entity_id: etype}
        edges: list[dict[str, Any]] = []
        omitted = 0

        def add_node(i: str, t: str) -> bool:
            nonlocal omitted
            if i in nodes:
                return True
            if len(nodes) >= max_nodes:
                omitted += 1
                return False
            nodes[i] = t
            return True

        def gene_edges(gene: str, disease: str, link: dict[str, str]) -> None:
            c = self.store.claims[link["claim_id"]]
            edges.append({"source": gene, "target": disease, "predicate": c.predicate, "claim_id": c.claim_id,
                          "status": c.status.value, "review_state": c.review_state.value, "score": None})

        if etype == DISEASE:
            out = self.connections(entity_id)
            for r in out["results"]:
                score = next((c["score"] for c in r["comparisons"] if c["channel_id"] == "phenotype"), None)
                if score is not None and add_node(r["candidate_id"], DISEASE):
                    edges.append({"source": entity_id, "target": r["candidate_id"], "predicate": "SIMILAR_SYMPTOMS",
                                  "claim_id": None, "status": "computational_prediction", "review_state": "unreviewed",
                                  "score": score})
            for d in list(nodes):  # step two: the genes of every disease shown (a few each), and their diseases
                genes = self.genes_of.get(d, [])
                omitted += max(0, len(genes) - GENES_PER_DISEASE)
                for g in genes[:GENES_PER_DISEASE]:
                    if add_node(g["id"], GENE):
                        gene_edges(g["id"], d, g)
            for g in [i for i, t in nodes.items() if t == GENE]:
                for d in self.diseases_of.get(g, [])[:4]:
                    if (d["id"] in nodes or add_node(d["id"], DISEASE)) and not any(
                            e["source"] == g and e["target"] == d["id"] for e in edges):
                        gene_edges(g, d["id"], d)
        else:
            for d in self.diseases_of.get(entity_id, []):
                if add_node(d["id"], DISEASE):
                    gene_edges(entity_id, d["id"], d)
            for d in [i for i, t in nodes.items() if t == DISEASE]:
                for g in self.genes_of.get(d, []):
                    if g["id"] != entity_id and add_node(g["id"], GENE):
                        gene_edges(g["id"], d, g)
        return {"nodes": [{"id": i, "label": self.r.label_of(i), "type": t} for i, t in nodes.items()],
                "edges": edges, "truncated": omitted > 0, "omitted": omitted}

    def descendants(self, entity_id: str, depth: int = 3) -> set[str]:
        out: set[str] = set()
        frontier = {entity_id}
        for _ in range(depth):
            frontier = {c for f in frontier for c in self.children.get(f, ())} - out
            out |= frontier
        return out

    def hierarchy_note(self, query: str, other: str) -> str | None:
        """Says when a 'related' disease is simply a subtype or a parent group of the query."""
        if other in self.descendants(query):
            return "a more specific form of this disease"
        if other in self.ancestors(query):
            return "a broader group that includes this disease"
        return None

    def subtype_genes(self, entity_id: str, depth: int = 2) -> list[dict[str, str]]:
        """Genes recorded on more specific forms of a disease (MONDO children, up to `depth` levels):
        HPO often links the gene to the subtype (NPC1 -> "Niemann-Pick disease, type C1"), not the parent."""
        found: dict[str, dict[str, str]] = {}
        frontier = {entity_id}
        for _ in range(depth):
            frontier = {c for f in frontier for c in self.children.get(f, ())}
            for d in sorted(frontier):
                for g in self.genes_of.get(d, []):
                    found.setdefault(g["id"], {**g, "via": d})
        return list(found.values())

    def summary(self, entity_id: str) -> list[dict[str, Any]]:
        """A plain-language summary written by template from the records shown on the page: nothing
        added, nothing inferred. Each sentence names its source; gene sentences cite their claims."""
        etype = next((t for t in ENTITY_TYPES if entity_id in self.r._labels[t]), None)
        lab = self.r.label_of
        out: list[dict[str, Any]] = []

        def say(text: str, claim_ids: list[str] | None = None, source: str = "") -> None:
            out.append({"text": text, "claim_ids": claim_ids or [], "source": source})

        if etype == DISEASE:
            terms = self.ph._terms.get(entity_id, set()) if self.ph else set()
            if terms:
                rare = sorted(self.ph.specific(terms), key=lambda t: (-self.ph.ic(t), t))[:3]
                names = _join([self.ph.labels.get(t, t).lower() for t in rare])
                say(f"The Human Phenotype Ontology records {len(terms)} features for it; the most distinctive "
                    f"(recorded for the fewest other diseases) are {names}.", source="HPO phenotype.hpoa")
            else:
                say("No symptoms are recorded for it in the Human Phenotype Ontology files used here.",
                    source="HPO phenotype.hpoa")
            genes = self.genes_of.get(entity_id, [])
            if genes:
                kinds = {g["association"] for g in genes}
                what = "a single-gene (Mendelian) link" if kinds == {"mendelian"} else "a recorded link"
                say(f"It is linked to {'the gene' if len(genes) == 1 else f'{len(genes)} genes:'} "
                    f"{_join([lab(g['id']) for g in genes[:5]])}{' and others' if len(genes) > 5 else ''} ({what}; "
                    "a link alone does not show that a gene causes the disease).",
                    [g["claim_id"] for g in genes[:5]], "HPO genes_to_disease")
            else:
                sub = self.subtype_genes(entity_id)
                if sub:
                    say("No gene is linked to this entry itself, but genes are recorded on its more specific forms: "
                        + _join([f"{lab(g['id'])} ({lab(g['via'])})" for g in sub[:4]])
                        + (" and others" if len(sub) > 4 else "") + ".",
                        [g["claim_id"] for g in sub[:4]], "HPO genes_to_disease + MONDO hierarchy")
                else:
                    say("No gene is linked to it in the HPO gene-disease file.", source="HPO genes_to_disease")
            kids = self.children.get(entity_id, set())
            if kids:
                say(f"MONDO lists {len(kids)} more specific {'form' if len(kids) == 1 else 'forms'} of it.",
                    source="MONDO hierarchy")
            conn = self.connections(entity_id)
            top = [r for r in conn["results"]
                   if r["category"] == "symptom-level lead" and r["candidate_id"] not in conn["hierarchy"]][:2]
            if top:
                lead = "Apart from its own subtypes, the" if conn["hierarchy"] else "The"
                say(f"{lead} diseases with the most similar recorded symptoms are "
                    f"{_join([lab(r['candidate_id']) for r in top])}. "
                    "Similar symptoms are not a diagnosis and do not show a shared cause.", source="Phenotype channel")
            grp = self.groups(entity_id)
            if grp["status"] == "ok" and grp["groups"]:
                say(f"GARD (NIH) lists {len(grp['groups'])} patient {'group' if len(grp['groups']) == 1 else 'groups'} "
                    "for it (a listing is not an endorsement).", source="GARD")
            a = self.assets(entity_id)
            if a.get("coverage", {}) and a["coverage"].get("status") == "ok":
                n = a.get("total", 0)
                opened = sum(1 for x in a["assets"] if "open" in x["ranking_reasons"])
                say(f"{n} {'study lists' if n == 1 else 'studies list'} it as a condition on ClinicalTrials.gov"
                    + (f"; {opened} {'is' if opened == 1 else 'are'} open now." if n else "."), source="ClinicalTrials.gov")
        elif etype == GENE:
            ds = self.diseases_of.get(entity_id, [])
            if ds:
                say(f"The HPO gene-disease file links {lab(entity_id)} to {len(ds)} "
                    f"{'disease' if len(ds) == 1 else 'diseases'}: {_join([lab(d['id']) for d in ds[:5]])}"
                    f"{' and others' if len(ds) > 5 else ''}. A link alone does not show that the gene causes them.",
                    [d["claim_id"] for d in ds[:5]], "HPO genes_to_disease")
            else:
                say(f"No disease is linked to {lab(entity_id)} in the HPO gene-disease file.", source="HPO genes_to_disease")
        elif etype == PHENOTYPE and self.ph:
            n = len(set(self.ph._by_term.get(entity_id, ())) - self.excluded)
            say(f"This symptom term is recorded for {n} {'disease' if n == 1 else 'diseases'} in the Human Phenotype "
                "Ontology, counting more specific forms of it.", source="HPO phenotype.hpoa")
        return out

    def actions(self, entity_id: str) -> list[dict[str, Any]]:
        """Q3 for a real disease: T10 template cards over the real Q1/Q2 facts (no LLM, no invented
        content). Evidence brief always; asset-reuse cards for up to two open studies. No outreach
        note: a registry record page is not a verified contact route."""
        if entity_id not in self.r._labels[DISEASE]:
            return []
        self.connections(entity_id)
        with self._lock:  # take one consistent snapshot: the paper claims can be swapped by another request
            outcome, ranked_claims = self._outcomes.get(entity_id), self._rank_store.claims
        if outcome is None:
            self.connections(entity_id)
            outcome, ranked_claims = self._outcomes[entity_id], self._rank_store.claims
        cards = [evidence_brief(outcome, ranked_claims, label_of=self.r.label_of, audience="science")]
        assets = self.assets(entity_id)
        claims = {k: Claim.model_validate(v) for k, v in assets.get("claims", {}).items()}
        for a in [x for x in assets.get("assets", []) if "open" in x["ranking_reasons"]][:2]:
            try:
                cards.append(asset_reuse(AssetResult.model_validate(a), claims, label_of=self._label, audience="science"))
            except CardError:
                continue
        return [c.model_dump(mode="json") for c in cards]

    def _label(self, entity_id: str) -> str:
        return self.r.label_of(entity_id)

    def groups(self, entity_id: str) -> dict[str, Any]:
        """Patient groups GARD lists for a real disease (see atlas.gard for the rules)."""
        if entity_id not in self.r._labels[DISEASE]:
            return {"status": "not_a_disease", "groups": [], "pages": []}
        return self.gard.for_disease(entity_id, self.gard_of.get(entity_id, []))

    def symptom_terms(self, text: str) -> list[dict[str, Any]]:
        """Turn described symptoms into HPO terms, deterministically. Phrases split on commas, semicolons, new
        lines and "and"; a sentence with no separators is scanned for the longest exact HPO names. An HPO ID is
        accepted as typed. A phrase that is ambiguous or only fuzzy-matches is reported, never auto-picked."""
        out: list[dict[str, Any]] = []

        def one(phrase: str) -> dict[str, Any]:
            if re.fullmatch(r"HP:\d{7}", phrase.strip().upper()):
                pid = phrase.strip().upper()
                ok = pid in self.r._labels[PHENOTYPE]
                return {"text": phrase, "status": "resolved" if ok else "unresolved", "id": pid if ok else None,
                        "label": self.r.label_of(pid) if ok else "", "method": "HPO identifier as typed"}
            res = self.r.resolve(phrase, PHENOTYPE)
            return {"text": phrase, "status": res.status, "id": res.resolved_id,
                    "label": self.r.label_of(res.resolved_id) if res.resolved_id else "", "method": res.method,
                    "candidates": [{"id": c.entity_id, "label": c.label} for c in res.candidates[:5]]
                    if res.status != "resolved" else []}

        parts = [p.strip() for p in re.split(r"[,;\n]|\band\b|\bwith\b", text, flags=re.IGNORECASE) if p.strip()]
        for raw_part in parts:
            # "no hearing loss" says the symptom is absent: it is resolved like any symptom but never used as a match
            neg = _NEGATION.match(raw_part)
            part = raw_part[neg.end():].strip() if neg else raw_part
            if not part:
                continue
            start = len(out)
            r = one(part)
            if r["status"] == "resolved":
                out.append(r)
            else:
                words = part.split()
                found: list[dict[str, Any]] = []
                if len(words) > 1:  # a run of words: try the longest exact names first, left to right
                    i = 0
                    while i < len(words):
                        for n in range(min(6, len(words) - i), 0, -1):
                            cand = one(" ".join(words[i:i + n]))
                            if cand["status"] == "resolved":
                                found.append(cand)
                                i += n
                                break
                        else:
                            i += 1
                out += found or [r]
            for item in out[start:]:
                item["absent"] = bool(neg)
        seen: set[str] = set()
        return [r for r in out if not (r["id"] and (r["id"] in seen or seen.add(r["id"])))]

    def symptom_search(self, text: str, limit: int = 15) -> dict[str, Any]:
        """Candidate diseases for described symptoms, with the genes linked to each. Research hypotheses only."""
        terms = self.symptom_terms(text)
        ids = [t["id"] for t in terms if t["id"] and not t.get("absent")]
        absent_ids = [t["id"] for t in terms if t["id"] and t.get("absent")]
        rows = self.ph.rank_by_symptoms(ids, exclude=self.excluded, limit=limit) if self.ph and ids else []
        lab = self.r.label_of
        cands = []
        for r in rows:
            genes = self.genes_of.get(r["disease_id"], [])[:5]
            # a symptom the person says is absent, but that the disease records (or records a more specific form of)
            clash = [t for t in absent_ids if r["disease_id"] in self.ph._by_term.get(t, ())] if self.ph else []
            cands.append({
                **r, "label": lab(r["disease_id"]), "recorded_despite_absent": [lab(t) for t in clash],
                "matched_labels": [lab(t) for t in r["matched"]], "unmatched_labels": [lab(t) for t in r["unmatched"]],
                "genes": [{"id": g["id"], "label": lab(g["id"]), "claim_id": g["claim_id"], "source": g["source"]} for g in genes],
                "label_kind": "research hypothesis, not a diagnosis",
            })
        cands.sort(key=lambda c: (-c["coverage"], len(c["recorded_despite_absent"])))  # stable: other ties keep their order
        return {
            "terms": terms, "candidates": cands,
            "definition": self.ph.SYMPTOM_DEFINITION if self.ph else "",
            "note": ("These are research hypotheses from recorded symptom patterns, not diagnoses. Many diseases share "
                     "symptoms, a missing symptom in a record is not evidence of absence, and nothing here uses a "
                     "person's data. Take them to a clinician or geneticist."),
            "source": "HPO phenotype.hpoa and genes_to_disease", "versions": self.r.versions,
        }

    def claim(self, claim_id: str) -> dict[str, Any] | None:
        c = self._rank_store.claims.get(claim_id)
        return c.model_dump(mode="json") if c else self.trials.claims.get(claim_id)

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


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""
