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
COMPARTMENT, CHEMICAL = "compartment", "chemical"  # GO cellular component; ChEBI compound
ENTITY_TYPES = (DISEASE, GENE, PHENOTYPE)  # the types public search and the API use
EXTRACTION_ONLY_TYPES = (COMPARTMENT, CHEMICAL)  # loaded only for extraction (from_raw include_extraction_refs)
_ALL_TYPES = ENTITY_TYPES + EXTRACTION_ONLY_TYPES
_PREFIX_FOR_TYPE = {DISEASE: "MONDO", GENE: "HGNC", PHENOTYPE: "HP", COMPARTMENT: "GO", CHEMICAL: "CHEBI"}
_ID_DIGITS = {"CHEBI": r"\d+"}  # every other prefix here uses 7 digits
_BRACKETED = re.compile(r"\(([^()]*)\)")

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


_DATASET_NAMES = {
    "mondo/": "MONDO", "hgnc/": "HGNC", "hpo/hp.json": "HPO ontology",
    "hpo/phenotype.hpoa": "HPO disease–symptom annotations", "hpo/genes_to_disease.txt": "HPO gene–disease annotations",
    "go/": "Gene Ontology", "chebi/": "ChEBI",
}


class Resolver:
    def __init__(self, versions: dict[str, str] | None = None):
        self.versions = versions or {}
        self._labels: dict[str, dict[str, str]] = {t: {} for t in _ALL_TYPES}  # id -> label
        self._index: dict[str, dict[str, list[tuple[str, str, int]]]] = {t: {} for t in _ALL_TYPES}
        self._xrefs: dict[str, set[str]] = {}
        self._tokens: dict[str, dict[str, set[str]]] = {t: {} for t in _ALL_TYPES}  # token -> norm names
        # (type, normalized) -> [(id, note, source_ids)]; empty source_ids = a general cluster alias
        self._aliases: dict[tuple[str, str], list[tuple[str, str, frozenset[str]]]] = {}

    @property
    def public_versions(self) -> dict[str, str]:
        """Release notes keyed by dataset name, for readers (the keys of `versions` are repository paths)."""
        return {next((n for p, n in _DATASET_NAMES.items() if k.startswith(p)), k.split("/", 1)[0].upper()): v
                for k, v in self.versions.items()}

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
        """Load an OBO-JSON file (MONDO, HPO, GO cellular components, ChEBI). Deprecated terms are skipped."""
        prefix = _PREFIX_FOR_TYPE[entity_type]
        digits = _ID_DIGITS.get(prefix, r"\d{7}")
        graph = json.loads(Path(path).read_text())["graphs"][0]
        count = 0
        for node in graph["nodes"]:
            if node.get("type") != "CLASS" or not node["id"].startswith(f"{_OBO_PURL}{prefix}_"):
                continue
            meta = node.get("meta", {})
            if meta.get("deprecated") or not node.get("lbl"):
                continue
            if entity_type == COMPARTMENT and not _in_namespace(meta, "cellular_component"):
                continue
            curie = node["id"][len(_OBO_PURL):].replace("_", ":", 1)
            if not re.fullmatch(digits, curie.split(":")[1]):
                continue
            names = [
                (s["val"], TIER_EXACT if s["pred"] == "hasExactSynonym" else TIER_RELATED)
                for s in meta.get("synonyms", [])
            ]
            xrefs = [x["val"] for x in meta.get("xrefs", []) if "val" in x]
            self.add(entity_type, curie, node["lbl"], names, xrefs)
            count += 1
        return count

    def load_aliases(self, path: Path) -> int:
        """Owner-approved aliases (data/aliases.json). Each must point at an ID that exists in the
        pinned files. A general alias applies only when the plain name match does not resolve. An
        alias with "sources" applies only to those sources and OVERRIDES the plain match there
        (the paper itself defines the term, e.g. JNCL = juvenile CLN3 disease)."""
        count = 0
        for a in json.loads(Path(path).read_text())["aliases"]:
            if self._labels[a["type"]] and a["id"] not in self._labels[a["type"]]:
                raise ValueError(f"alias {a['mention']!r} -> {a['id']} is not in the pinned {a['type']} file")
            entry = (a["id"], a["note"], frozenset(a.get("sources", ())))
            self._aliases.setdefault((a["type"], normalize(a["mention"])), []).append(entry)
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
    def from_raw(cls, raw_dir: Path, include_hpo: bool = True, include_extraction_refs: bool = False) -> "Resolver":
        """`include_extraction_refs` adds GO components, ChEBI chemicals and the owner alias table.
        Off by default: public search and the API must see strict, un-aliased names and must not
        pay to load ~200,000 chemical names."""
        raw = Path(raw_dir)
        checks = raw / "CHECKSUMS.json"
        versions = ({k: re.sub(r";\s*see [\w./-]+\.\w+", "", v["note"]) for k, v in json.loads(checks.read_text()).items()}
                    if checks.exists() else {})  # shown to readers: release notes without repository file references
        r = cls(versions)
        r.load_obo_json(raw / "mondo" / "mondo.json", DISEASE)
        r.load_hgnc(raw / "hgnc" / "hgnc_complete_set.txt")
        if include_hpo:
            r.load_obo_json(raw / "hpo" / "hp.json", PHENOTYPE)
        if include_extraction_refs:
            for rel, kind in (("go/go-basic.json", COMPARTMENT), ("chebi/chebi_lite.json", CHEMICAL)):
                if (raw / rel).exists():  # optional: older checkouts have neither file
                    r.load_obo_json(raw / rel, kind)
            aliases = raw.parent / "aliases.json"
            if aliases.exists():
                r.load_aliases(aliases)
        return r

    # ---- resolving ----
    def resolve(self, mention: str, entity_type: str, source_id: str | None = None) -> Resolution:
        if entity_type not in _ALL_TYPES:
            raise ValueError(f"unknown entity_type {entity_type!r}")
        mention = mention.strip()
        if not mention:
            return Resolution(mention, entity_type, "unresolved", None, "empty mention")
        if ":" in mention and re.fullmatch(r"[A-Za-z]+:\S+", mention):
            return self._resolve_curie(mention, entity_type)

        plain = self._resolve_name(mention, entity_type, source_id)
        if plain.status == "resolved":
            return plain
        # "Niemann-Pick Type C (NPC) disease": the text outside the brackets is the name and the
        # bracket is usually an abbreviation of it, so the outer name wins. Only if it does not
        # resolve are the bracketed parts tried, and then they must agree on one entity.
        pieces = _bracket_pieces(mention)
        if pieces:
            outer = self._resolve_name(pieces[0], entity_type, source_id)
            if outer.status == "resolved":
                return Resolution(
                    mention, entity_type, "resolved", outer.resolved_id,
                    f"bracketed mention: matched '{pieces[0]}' ({outer.method})", outer.candidates,
                )
            hits = {}
            for piece in pieces[1:]:
                r = self._resolve_name(piece, entity_type, source_id)
                if r.status == "resolved" and r.resolved_id:
                    hits[r.resolved_id] = (piece, r)
            if len(hits) == 1:
                (rid, (piece, r)), = hits.items()
                return Resolution(
                    mention, entity_type, "resolved", rid,
                    f"bracketed mention: matched the bracketed '{piece}' ({r.method})", r.candidates,
                )
            if len(hits) > 1:
                cands = [self._candidate(entity_type, rid, piece, TIER_RELATED) for rid, (piece, _) in sorted(hits.items())]
                return Resolution(
                    mention, entity_type, "ambiguous", None,
                    f"bracketed mention: the bracketed parts name {len(hits)} different entities; not merged", cands,
                )
        return plain if plain.status != "unresolved" else self._from_fuzzy(mention, entity_type)

    def _resolve_name(self, mention: str, entity_type: str, source_id: str | None = None) -> Resolution:
        """Source-scoped alias (overrides), else exact name match, else a general alias."""
        norm = normalize(mention)
        aliases = self._aliases.get((entity_type, norm), [])
        scoped = [(i, n) for i, n, srcs in aliases if source_id and source_id in srcs]
        if scoped:
            return self._alias_result(mention, entity_type, *scoped[0], scope=f"source {source_id}")
        entries = self._index[entity_type].get(norm, [])
        res = self._from_exact(mention, entity_type, entries) if entries else Resolution(
            mention, entity_type, "unresolved", None, "no exact match"
        )
        general = [(i, n) for i, n, srcs in aliases if not srcs]
        if res.status != "resolved" and general:
            return self._alias_result(mention, entity_type, *general[0])
        return res

    def _alias_result(self, mention: str, entity_type: str, rid: str, note: str, scope: str = "") -> Resolution:
        where = f"; scoped to {scope}" if scope else ""
        return Resolution(
            mention, entity_type, "resolved", rid, f"owner-approved alias ({note}{where})",
            [self._candidate(entity_type, rid, mention, TIER_EXACT)],
        )

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


def _in_namespace(meta: dict, namespace: str) -> bool:
    return any(
        p.get("pred", "").endswith("hasOBONamespace") and p.get("val") == namespace
        for p in meta.get("basicPropertyValues", [])
    )


def _bracket_pieces(mention: str) -> list[str]:
    """['Niemann-Pick Type C disease', 'NPC'] for 'Niemann-Pick Type C (NPC) disease'; [] if no brackets."""
    inner = [m.strip() for m in _BRACKETED.findall(mention) if m.strip()]
    if not inner:
        return []
    outer = " ".join(_BRACKETED.sub(" ", mention).split())
    return [p for p in (outer, *inner) if p]


def _split(value: str) -> list[str]:
    return [p.strip().strip('"') for p in value.split("|") if p.strip().strip('"')]


def validate_variant_ref(assembly: str | None, transcript: str | None) -> None:
    """Variants need a genome assembly and a versioned transcript; versions are never merged."""
    if assembly not in _ASSEMBLIES:
        raise ValueError(f"variant needs an assembly in {sorted(_ASSEMBLIES)}, got {assembly!r}")
    if not transcript or not _TRANSCRIPT.fullmatch(transcript):
        raise ValueError(f"variant needs a versioned transcript like NM_000086.3, got {transcript!r}")
