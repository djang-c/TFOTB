"""T03 ID resolver: mention string -> ontology ID, without ever guessing.

Rules (PLAN T03, docs/implementation/06 section 2):
- IDs come only from the pinned ontology files; they are never built from labels.
- Exact match on label / synonym / alias, in tiers. A tier with exactly one entity resolves;
  more than one stays ambiguous and returns every candidate (never merged).
- Fuzzy matches are suggestions only (no auto-accept). This is stricter than the doc 06 draft,
  which accepted a single high-score hit; recorded in docs/DECISIONS.md.
- Unresolved stays unresolved. The optional LLM pick (T04 scope) is not implemented here.
"""

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from atlas.schemas import validate_curie

DISEASE, GENE, PHENOTYPE = "disease", "gene", "phenotype"
ENTITY_TYPES = (DISEASE, GENE, PHENOTYPE)
_PREFIX_FOR_TYPE = {DISEASE: "MONDO", GENE: "HGNC", PHENOTYPE: "HP"}

# Lower tier = stronger evidence that the mention names this entity.
TIER_LABEL, TIER_EXACT, TIER_RELATED = 0, 1, 2
_TIER_NAME = {TIER_LABEL: "label", TIER_EXACT: "exact synonym or symbol", TIER_RELATED: "related synonym"}

FUZZY_MIN_RATIO = 0.9
FUZZY_MAX_SUGGESTIONS = 8
_OBO_PURL = "http://purl.obolibrary.org/obo/"
_TRANSCRIPT = re.compile(r"(NM|NR|XM|XR|NP)_\d+\.\d+")
_ASSEMBLIES = frozenset({"GRCh37", "GRCh38"})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text).split())


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    matched: str  # the label/synonym text that matched
    tier: int


@dataclass
class Resolution:
    mention: str
    entity_type: str
    status: str  # "resolved" | "ambiguous" | "suggestions" | "unresolved"
    resolved_id: str | None
    method: str
    candidates: list[Candidate] = field(default_factory=list)


class Resolver:
    def __init__(self, versions: dict[str, str] | None = None):
        self.versions = versions or {}
        self._labels: dict[str, dict[str, str]] = {t: {} for t in ENTITY_TYPES}  # id -> label
        self._index: dict[str, dict[str, list[tuple[str, str, int]]]] = {t: {} for t in ENTITY_TYPES}
        self._xrefs: dict[str, set[str]] = {}
        self._tokens: dict[str, dict[str, set[str]]] = {t: {} for t in ENTITY_TYPES}  # token -> norm names

    # ---- building ----
    def add(self, entity_type: str, entity_id: str, label: str, names: list[tuple[str, int]], xrefs: list[str] = ()):
        validate_curie(entity_id)
        if not entity_id.startswith(_PREFIX_FOR_TYPE[entity_type] + ":"):
            raise ValueError(f"{entity_id} is not a {entity_type} identifier")
        self._labels[entity_type][entity_id] = label
        for text, tier in [(label, TIER_LABEL), *names]:
            norm = normalize(text)
            if not norm:
                continue
            entries = self._index[entity_type].setdefault(norm, [])
            if (entity_id, text, tier) not in entries:
                entries.append((entity_id, text, tier))
            for tok in norm.split():
                self._tokens[entity_type].setdefault(tok, set()).add(norm)
        for x in xrefs:
            self._xrefs.setdefault(x.casefold(), set()).add(entity_id)

    def load_obo_json(self, path: Path, entity_type: str) -> int:
        """Load a MONDO or HPO OBO-JSON file. Deprecated terms are skipped."""
        prefix = _PREFIX_FOR_TYPE[entity_type]
        graph = json.loads(Path(path).read_text())["graphs"][0]
        count = 0
        for node in graph["nodes"]:
            if node.get("type") != "CLASS" or not node["id"].startswith(f"{_OBO_PURL}{prefix}_"):
                continue
            meta = node.get("meta", {})
            if meta.get("deprecated") or not node.get("lbl"):
                continue
            curie = node["id"][len(_OBO_PURL):].replace("_", ":", 1)
            if not re.fullmatch(r"\d{7}", curie.split(":")[1]):
                continue
            names = [
                (s["val"], TIER_EXACT if s["pred"] == "hasExactSynonym" else TIER_RELATED)
                for s in meta.get("synonyms", [])
            ]
            xrefs = [x["val"] for x in meta.get("xrefs", []) if "val" in x]
            self.add(entity_type, curie, node["lbl"], names, xrefs)
            count += 1
        return count

    def load_hgnc(self, path: Path) -> int:
        """Load the HGNC complete set. Only Approved genes are eligible."""
        count = 0
        with Path(path).open(newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["status"] != "Approved":
                    continue
                names = [(x, TIER_EXACT) for col in ("alias_symbol", "prev_symbol") for x in _split(row[col])]
                names += [(x, TIER_RELATED) for col in ("alias_name", "prev_name") for x in _split(row[col])]
                names.append((row["name"], TIER_EXACT))
                xrefs = [f"Ensembl:{row['ensembl_gene_id']}"] if row["ensembl_gene_id"] else []
                self.add(GENE, row["hgnc_id"], row["symbol"], names, xrefs)
                count += 1
        return count

    @classmethod
    def from_raw(cls, raw_dir: Path, include_hpo: bool = True) -> "Resolver":
        raw = Path(raw_dir)
        checks = raw / "CHECKSUMS.json"
        versions = {k: v["note"] for k, v in json.loads(checks.read_text()).items()} if checks.exists() else {}
        r = cls(versions)
        r.load_obo_json(raw / "mondo" / "mondo.json", DISEASE)
        r.load_hgnc(raw / "hgnc" / "hgnc_complete_set.txt")
        if include_hpo:
            r.load_obo_json(raw / "hpo" / "hp.json", PHENOTYPE)
        return r

    # ---- resolving ----
    def resolve(self, mention: str, entity_type: str) -> Resolution:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"unknown entity_type {entity_type!r}")
        mention = mention.strip()
        if not mention:
            return Resolution(mention, entity_type, "unresolved", None, "empty mention")
        if ":" in mention and re.fullmatch(r"[A-Za-z]+:\S+", mention):
            return self._resolve_curie(mention, entity_type)

        entries = self._index[entity_type].get(normalize(mention), [])
        if entries:
            return self._from_exact(mention, entity_type, entries)
        return self._from_fuzzy(mention, entity_type)

    def ids_for_xref(self, xref: str) -> set[str]:
        return set(self._xrefs.get(xref.strip().casefold(), ()))

    def label_of(self, entity_id: str) -> str:
        return next((labels[entity_id] for labels in self._labels.values() if entity_id in labels), "")

    def resolve_xref(self, xref: str) -> Resolution:
        ids = sorted(self._xrefs.get(xref.strip().casefold(), ()))
        cands = [self._candidate(DISEASE, i, xref, TIER_EXACT) for i in ids]
        if len(ids) == 1:
            return Resolution(xref, DISEASE, "resolved", ids[0], f"cross-reference {xref}", cands)
        if ids:
            return Resolution(xref, DISEASE, "ambiguous", None, f"cross-reference {xref} maps to {len(ids)} entries", cands)
        return Resolution(xref, DISEASE, "unresolved", None, f"cross-reference {xref} not found")

    def _candidate(self, entity_type: str, entity_id: str, matched: str, tier: int) -> Candidate:
        return Candidate(entity_id, self._labels[entity_type].get(entity_id, ""), matched, tier)

    def _resolve_curie(self, mention: str, entity_type: str) -> Resolution:
        try:
            validate_curie(mention)
        except ValueError:
            return Resolution(mention, entity_type, "unresolved", None, "malformed identifier (IDs are never built from labels)")
        if mention in self._labels[entity_type]:
            c = self._candidate(entity_type, mention, mention, TIER_LABEL)
            return Resolution(mention, entity_type, "resolved", mention, "identifier found in pinned file", [c])
        return Resolution(mention, entity_type, "unresolved", None, "identifier not in pinned file for this type")

    def _from_exact(self, mention: str, entity_type: str, entries: list[tuple[str, str, int]]) -> Resolution:
        best_tier = min(t for _, _, t in entries)
        best = sorted({(i, text) for i, text, t in entries if t == best_tier})
        best_ids = sorted({i for i, _ in best})
        cands = [self._candidate(entity_type, i, text, best_tier) for i, text in best]
        others = sorted({i for i, _, t in entries if t > best_tier} - set(best_ids))
        # A label is a primary name, so a unique label wins. A synonym or abbreviation may only
        # resolve if no other entity uses it at any tier ("NPC" names three different diseases).
        if len(best_ids) == 1 and (best_tier == TIER_LABEL or not others):
            note = f"; {len(others)} other entries match only as weaker synonyms: {others}" if others else ""
            return Resolution(
                mention, entity_type, "resolved", best_ids[0],
                f"matched {_TIER_NAME[best_tier]} '{best[0][1]}'{note}", cands,
            )
        all_ids = sorted({*best_ids, *others})
        cands += [self._candidate(entity_type, i, text, t) for i, text, t in entries if i in others]
        return Resolution(
            mention, entity_type, "ambiguous", None,
            f"{len(all_ids)} entities use this name; not merged, please clarify", cands,
        )

    def _from_fuzzy(self, mention: str, entity_type: str) -> Resolution:
        norm = normalize(mention)
        pool: set[str] = set()
        for tok in norm.split():
            pool |= self._tokens[entity_type].get(tok, set())
        scored = sorted(
            ((SequenceMatcher(None, norm, name).ratio(), name) for name in pool), reverse=True
        )
        cands: list[Candidate] = []
        seen: set[str] = set()
        for ratio, name in scored:
            if ratio < FUZZY_MIN_RATIO:
                break
            for entity_id, text, tier in self._index[entity_type][name]:
                if entity_id not in seen and len(cands) < FUZZY_MAX_SUGGESTIONS:
                    seen.add(entity_id)
                    cands.append(self._candidate(entity_type, entity_id, text, tier))
        if cands:
            return Resolution(mention, entity_type, "suggestions", None, "fuzzy suggestions only; please confirm", cands)
        return Resolution(mention, entity_type, "unresolved", None, "no exact or close match in pinned files")


def _split(value: str) -> list[str]:
    return [p.strip().strip('"') for p in value.split("|") if p.strip().strip('"')]


def validate_variant_ref(assembly: str | None, transcript: str | None) -> None:
    """Variants need a genome assembly and a versioned transcript; versions are never merged."""
    if assembly not in _ASSEMBLIES:
        raise ValueError(f"variant needs an assembly in {sorted(_ASSEMBLIES)}, got {assembly!r}")
    if not transcript or not _TRANSCRIPT.fullmatch(transcript):
        raise ValueError(f"variant needs a versioned transcript like NM_000086.3, got {transcript!r}")
