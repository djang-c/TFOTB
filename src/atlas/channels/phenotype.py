"""T06 phenotype channel: information-content (IC) weighted HPO similarity between two diseases.

Implements docs/implementation/05 section 1. No combined score; this channel reports only its own
number, defined in `score_definition`. Only positive, phenotypic-abnormality annotations are used.
An explicitly absent term (qualifier NOT) is kept separately and never treated as a match; a term
that is not mentioned is unknown. Disease names from phenotype.hpoa are NOT kept (OMIM-derived text);
only the source IDs and HPO term links are used.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from atlas.channels.base import EvidenceChannel
from atlas.resolver import Resolver
from atlas.schemas import ChannelComparison

_PURL = "http://purl.obolibrary.org/obo/"
LOW_IC_P = 0.05  # a term annotated to >5% of diseases is flagged "common, less informative"
MAX_CANDIDATES_DEFAULT = 100


def _curie(purl: str) -> str:
    return purl[len(_PURL):].replace("_", ":", 1)


class PhenotypeChannel(EvidenceChannel):
    channel_id = "phenotype"
    kind = "phenotype"

    def __init__(
        self,
        parents: dict[str, set[str]],
        labels: dict[str, str],
        source_terms: dict[str, set[str]],
        source_absent: dict[str, set[str]],
        xref_map: dict[str, set[str]],
        versions: str,
    ) -> None:
        """`source_terms`: annotation-source disease ID (OMIM:/ORPHA:/DECIPHER:) -> positive HPO terms.
        `xref_map`: the same source IDs -> MONDO IDs (from MONDO cross-references)."""
        self.version = "1"
        self.labels, self._parents, self._versions = labels, parents, versions
        self._anc_cache: dict[str, frozenset[str]] = {}
        self.n_diseases = len(source_terms)
        counts: dict[str, int] = defaultdict(int)
        for terms in source_terms.values():
            closure: set[str] = set()
            for t in terms:
                closure |= self.ancestors(t)
            for t in closure:
                counts[t] += 1
        self._p = {t: c / self.n_diseases for t, c in counts.items()} if self.n_diseases else {}
        self._terms: dict[str, set[str]] = defaultdict(set)
        self._absent: dict[str, set[str]] = defaultdict(set)
        self._unmapped = self._multi = 0
        for src, terms in source_terms.items():
            monds = {m for x in _xref_variants(src) for m in xref_map.get(x, ())}
            if not monds:
                self._unmapped += 1
            for m in monds:
                self._terms[m] |= terms
                self._absent[m] |= source_absent.get(src, set())
        self._by_term: dict[str, set[str]] = defaultdict(set)
        for m, terms in self._terms.items():
            for t in self._closure(terms):
                self._by_term[t].add(m)

    # ---- construction from the pinned files ----
    @classmethod
    def from_raw(cls, raw_dir: Path, resolver: Resolver) -> PhenotypeChannel:
        raw = Path(raw_dir)
        graph = json.loads((raw / "hpo" / "hp.json").read_text())["graphs"][0]
        labels = {
            _curie(n["id"]): n["lbl"]
            for n in graph["nodes"]
            if n["id"].startswith(_PURL + "HP_") and n.get("lbl")
        }
        parents: dict[str, set[str]] = defaultdict(set)
        for e in graph["edges"]:
            if e["pred"] == "is_a" and e["sub"].startswith(_PURL + "HP_") and e["obj"].startswith(_PURL + "HP_"):
                parents[_curie(e["sub"])].add(_curie(e["obj"]))
        terms: dict[str, set[str]] = defaultdict(set)
        absent: dict[str, set[str]] = defaultdict(set)
        with (raw / "hpo" / "phenotype.hpoa").open(newline="") as f:
            lines = (ln for ln in f if not ln.startswith("#"))
            for row in csv.DictReader(lines, delimiter="\t"):
                if row["aspect"] != "P":
                    continue
                (absent if row["qualifier"] == "NOT" else terms)[row["database_id"]].add(row["hpo_id"])
        xref_map: dict[str, set[str]] = defaultdict(set)
        for src in terms:
            for x in _xref_variants(src):
                xref_map[x] |= {i for i in resolver.ids_for_xref(x) if i.startswith("MONDO:")}
        used = ("hpo/hp.json", "hpo/phenotype.hpoa")
        versions = "; ".join(v for k, v in resolver.versions.items() if k in used) or "HPO version not recorded"
        return cls(parents, labels, dict(terms), dict(absent), dict(xref_map), versions)

    # ---- symptoms first: which diseases record these symptoms? ----
    SYMPTOM_DEFINITION = (
        "coverage = (sum of information content of the described symptoms that the disease records, counting more "
        "specific forms) / (sum over all described symptoms). Rare symptoms weigh more. profile_share = (information "
        "content of the described symptoms the disease records) / (information content of everything the disease "
        "records), so a disease whose profile is mostly what you described ranks above one that records hundreds of "
        "other symptoms. Both are shares of recorded annotations, not probabilities that the disease is present."
    )

    def rank_by_symptoms(self, terms: list[str], *, exclude: set[str] = frozenset(), limit: int = 15) -> list[dict[str, Any]]:
        """Diseases ranked by how much of a described symptom set they record. A hypothesis generator, not a
        diagnosis: nothing here uses patient data, and the number is explained in `SYMPTOM_DEFINITION`."""
        terms = list(dict.fromkeys(t for t in terms if t in self.labels))
        if not terms:
            return []
        weights = {t: self.ic(t) for t in terms}
        total = sum(weights.values())
        if total <= 0:  # only generic terms: fall back to plain counting so the answer is still defined
            weights, total = dict.fromkeys(terms, 1.0), float(len(terms))
        diseases: set[str] = set()
        for t in terms:
            diseases |= self._by_term.get(t, set())
        rows = []
        for d in diseases - set(exclude):
            matched = [t for t in terms if d in self._by_term.get(t, ())]
            # a symptom is recorded absent if it, or a more general form of it, is recorded as NOT present; the
            # reverse does not hold (a specific form being absent says nothing about the general symptom)
            absent = [t for t in terms if self.ancestors(t) & self._absent.get(d, set())]
            profile = sum(self.ic(t) for t in self._terms.get(d, ())) or 0.0
            matched_ic = sum(self.ic(t) for t in matched)
            share = min(1.0, matched_ic / profile) if profile > 0 else 0.0
            rows.append({
                "disease_id": d, "matched": matched, "unmatched": [t for t in terms if t not in matched],
                "recorded_absent": absent, "coverage": round(sum(weights[t] for t in matched) / total, 4),
                "profile_share": round(share, 4), "recorded_symptoms": len(self._terms.get(d, ())),
            })
        rows.sort(key=lambda r: (-r["coverage"], len(r["recorded_absent"]), -r["profile_share"], r["recorded_symptoms"], r["disease_id"]))
        return rows[:limit]

    # ---- ontology maths ----
    def ancestors(self, term: str) -> frozenset[str]:
        """The term and all its is_a ancestors."""
        hit = self._anc_cache.get(term)
        if hit is None:
            acc = {term}
            for p in self._parents.get(term, ()):
                acc |= self.ancestors(p)
            hit = self._anc_cache[term] = frozenset(acc)
        return hit

    def _closure(self, terms: set[str]) -> set[str]:
        out: set[str] = set()
        for t in terms:
            out |= self.ancestors(t)
        return out

    def ic(self, term: str) -> float:
        p = self._p.get(term)
        return -math.log(p) if p else 0.0

    def lin(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        common = self.ancestors(a) & self.ancestors(b)
        denom = self.ic(a) + self.ic(b)
        if not common or denom == 0:
            return 0.0
        return 2 * max(self.ic(c) for c in common) / denom

    def specific(self, terms: set[str]) -> set[str]:
        """Drop terms that have a more specific annotated descendant (no double counting)."""
        return {t for t in terms if not any(t != o and t in self.ancestors(o) for o in terms)}

    def bma_lin(self, a: set[str], b: set[str]) -> float:
        a, b = self.specific(a), self.specific(b)
        def one_way(x: set[str], y: set[str]) -> float:
            return sum(max(self.lin(i, j) for j in y) for i in x) / len(x)
        return (one_way(a, b) + one_way(b, a)) / 2

    # ---- channel contract ----
    def retrieve_candidates(self, query_id: str, context: dict[str, Any]) -> list[str]:
        q = self._terms.get(query_id)
        if not q:
            return []
        informative = {t for t in self._closure(q) if self._p.get(t, 1) <= LOW_IC_P}
        shared_count: dict[str, int] = defaultdict(int)
        for t in informative:
            for m in self._by_term.get(t, ()):
                if m != query_id:
                    shared_count[m] += 1
        ranked = sorted(shared_count, key=lambda m: (-shared_count[m], m))  # ordering only, not a score
        return ranked[: context.get("max_candidates", MAX_CANDIDATES_DEFAULT)]

    def compare(self, query_id: str, candidate_id: str, context: dict[str, Any]) -> ChannelComparison:
        base = {
            "channel_id": self.channel_id,
            "channel_version": self.version,
            "query_id": query_id,
            "candidate_id": candidate_id,
        }
        q, c = self._terms.get(query_id), self._terms.get(candidate_id)
        if not q or not c:
            missing = [x for x, t in ((query_id, q), (candidate_id, c)) if not t]
            return ChannelComparison(
                **base, availability="missing", missing_fields=[f"hpo_annotations:{m}" for m in missing],
                limitations=["no usable HPO annotations mapped to this disease; missing is not zero"],
            )
        shared = self._closure(q) & self._closure(c)
        informative = sorted((t for t in shared if self._p.get(t, 1) <= LOW_IC_P), key=lambda t: (-self.ic(t), t))[:5]
        common = sorted(t for t in shared if self._p.get(t, 0) > LOW_IC_P)
        limits = [f"{t} {self.labels.get(t, '')}: common (>5% of diseases), less informative" for t in common[:5]]
        contradicted = sorted(self._absent.get(query_id, set()) & c | self._absent.get(candidate_id, set()) & q)
        if contradicted:
            limits.append("explicitly absent in one disease but annotated in the other: " + ", ".join(contradicted))
        if self._unmapped:
            limits.append(f"{self._unmapped} annotation source IDs could not be mapped to MONDO and are excluded")
        return ChannelComparison(
            **base,
            availability="available",
            score=self.bma_lin(q, c),
            score_definition=(
                f"BMA-Lin over HPO is_a, IC=-ln(p) with p from the HPO disease–symptom annotations over {self.n_diseases} annotated "
                f"source diseases; {self._versions}"
            ),
            context_matches=[f"{t} {self.labels.get(t, '')}".strip() for t in informative],
            limitations=limits,
        )


def _xref_variants(source_id: str) -> list[str]:
    """phenotype.hpoa IDs (OMIM:123, ORPHA:456) -> the spellings MONDO uses for cross-references."""
    prefix, _, num = source_id.partition(":")
    return [f"Orphanet:{num}"] if prefix == "ORPHA" else [source_id]
