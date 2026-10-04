"""Mechanism clusters: groups of diseases that share an observed mechanism feature, from stored claims.

Brief, Module 3.1: cluster diseases by mechanism rather than by name, so a lysosomal storage disease and a
differently-named disease with the same pathway show up as neighbours. This is a deliberately simple, fully
inspectable rule, not a statistical model:

- A FEATURE is the non-disease end of an observed, credible claim (a compartment, a mechanism), together with
  the substance when the claim names one ("cholesterol in the lysosome" and "another lipid in the lysosome"
  are different features).
- Two diseases are linked when they share a feature. A cluster is a connected group of such diseases.
- Only claims that can count as evidence take part (`ranking.is_evidential`, reported observations, credible
  source). AI hypotheses, predictions, uploads and simulation records never create a link.
- A feature shared by more than `max_feature_degree` diseases is skipped as too generic to say anything.

A cluster is an ORGANISATION of the evidence. Membership does not mean the diseases share a treatment, a
cause or a prognosis, and the grouping has not been validated against any independent reference.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from atlas.ranking import CREDIBLE_SOURCES, is_evidential
from atlas.schemas import Claim, ClaimStatus

MECHANISM_PREDICATES = frozenset({"ACCUMULATES_IN_COMPARTMENT", "PERTURBS_MECHANISM"})
RULE = (
    "Diseases are grouped when observed claims from published sources place them on the same feature "
    "(for accumulation, the same compartment and the same substance). Hypotheses, predictions and uploads are ignored."
)
LIMITATION = (
    "An organisational view of the evidence. Being in a cluster does not mean the diseases share a treatment or a "
    "cause, and the grouping has not been validated against an independent reference."
)


def _feature(c: Claim, disease: str) -> str:
    other = c.object_id if c.subject_id == disease else c.subject_id
    sub = c.context.get("substance")
    return f"{other}[{sub}]" if sub else other


def mechanism_clusters(
    claims: dict[str, Claim], *, label_of=lambda _i: "", max_feature_degree: int = 30, min_diseases: int = 2,
) -> list[dict[str, Any]]:
    by_feature: dict[str, dict[str, list[Claim]]] = defaultdict(lambda: defaultdict(list))
    for c in claims.values():
        if (
            c.predicate not in MECHANISM_PREDICATES or not is_evidential(c)
            or c.status is not ClaimStatus.reported_observation or c.source_type not in CREDIBLE_SOURCES
        ):
            continue
        for disease in (c.subject_id, c.object_id):
            if disease.startswith("MONDO:"):
                by_feature[_feature(c, disease)][disease].append(c)

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    shared = {f: ds for f, ds in by_feature.items() if 2 <= len(ds) <= max_feature_degree}
    for ds in shared.values():
        first, *rest = sorted(ds)
        for d in rest:
            parent[find(d)] = find(first)
        find(first)

    groups: dict[str, set[str]] = defaultdict(set)
    for d in list(parent):
        groups[find(d)].add(d)
    out = []
    for members in groups.values():
        if len(members) < min_diseases:
            continue
        feats = []
        for f, ds in sorted(shared.items()):
            if set(ds) & members:
                ids = sorted({c.claim_id for cs in ds.values() for c in cs})
                lineages = {c.lineage_id for cs in ds.values() for c in cs}
                feats.append({
                    "feature": f, "label": " ".join(
                        x for x in (label_of(f.split("[")[0]) or f.split("[")[0],
                                    f"({label_of(f.split('[')[1].rstrip(']')) or f.split('[')[1].rstrip(']')})" if "[" in f else "")
                        if x
                    ),
                    "diseases": sorted(ds), "claim_ids": ids, "studies": len(lineages),
                })
        out.append({
            "diseases": [{"id": d, "label": label_of(d) or d} for d in sorted(members)],
            "shared_features": feats, "rule": RULE, "limitation": LIMITATION,
        })
    out.sort(key=lambda c: (-len(c["diseases"]), c["diseases"][0]["id"]))
    return out


# ---- groups around one entry ------------------------------------------------------------------------------------

GROUP_NOTE = (
    "Groups this entry belongs to, read from its computed connections: each group is the diseases that share one "
    "named feature with it. A group is an organisation of the evidence, not a statement that the diseases share a "
    "cause or a treatment. Missing is not the same as none: a disease absent here may simply not have been read."
)
_ID = r"(?:GO|CHEBI|HGNC|MONDO|HP):\w+"


def groups_for(entity_id: str, results: list[dict[str, Any]], *, label_of=lambda _i: "",
               similar_min: float = 0.4, similar_max: int = 12,
               feature_claims: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Clusters around one entry, from its connection results (atlas.connections), strongest kind first.

    - mechanism: diseases sharing an observed compartment/substance feature from published claims;
    - gene: diseases sharing a gene (gene-level only; not variant-level evidence);
    - direct: diseases a stored claim links directly (often a hypothesis-only relationship; labelled as such);
    - symptoms: the most symptom-similar diseases (similarity, not a shared cause), above `similar_min`.
    Every member keeps its evidence category and the claim IDs behind its membership: for a mechanism, the observed
    claims on that feature (`feature_claims`, from `mechanism_clusters`); for a direct link, the claim that states it."""
    import re

    def name(i: str) -> str:
        return label_of(i) or i

    def readable(feature: str) -> str:
        m = re.fullmatch(rf"({_ID})\[({_ID})\]", feature)
        return f"{name(m.group(1))} ({name(m.group(2))})" if m else name(feature)

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    similar: list[dict[str, Any]] = []

    def add(kind: str, key: str, label: str, member: dict[str, Any]) -> None:
        g = groups.setdefault((kind, key), {"kind": kind, "feature": key, "label": label, "members": []})
        g["members"].append(member)

    for r in results:
        cand = r["candidate_id"]
        base = {"id": cand, "label": name(cand), "category": r["category"]}
        for c in r["comparisons"]:
            if c["availability"] != "available":
                continue
            refs = list(dict.fromkeys(c["supporting_claim_ids"] + c["contradicting_claim_ids"]))
            if c["channel_id"] == "phenotype" and c["score"] is not None and c["score"] >= similar_min:
                shared = [re.sub(rf"^{_ID}\s*", "", m) for m in c["context_matches"][:3]]
                similar.append({**base, "score": round(c["score"], 2), "shared": shared, "claim_ids": refs})
            for m in c["context_matches"]:
                if c["channel_id"] == "dna_variants" and (g := re.fullmatch(rf"shared ({_ID})", m)):
                    # the gene channel names the claims on both sides in its limitation note, not as support
                    noted = [x for lim in c.get("limitations", []) if g.group(1) in lim for x in re.findall(r"CLAIM:[\w-]+", lim)]
                    add("gene", g.group(1), name(g.group(1)), {**base, "claim_ids": refs or list(dict.fromkeys(noted))})
                elif c["channel_id"] == "molecular_mechanisms":
                    if f := re.fullmatch(rf"shared ({_ID}(?:\[{_ID}\])?)", m):
                        own = (feature_claims or {}).get(f.group(1))
                        add("mechanism", f.group(1), readable(f.group(1)), {**base, "claim_ids": own if own is not None else refs})
                    elif d := re.match(r"directly links the two diseases: ([A-Z_]+)(?: \(([^)]*)\))?", m):
                        stated = [x.strip() for x in (d.group(2) or "").split(",") if x.strip().startswith("CLAIM:")]
                        add("direct", d.group(1), d.group(1), {**base, "claim_ids": stated or refs})
    order = {"mechanism": 0, "gene": 1, "direct": 2}
    out = sorted(groups.values(), key=lambda g: (order[g["kind"]], -len(g["members"]), g["label"]))
    similar.sort(key=lambda s: -s["score"])
    if similar:
        out.append({"kind": "symptoms", "feature": f"phenotype>={similar_min}", "label": "similar recorded symptoms",
                    "members": similar[:similar_max]})
    return out
