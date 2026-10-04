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
