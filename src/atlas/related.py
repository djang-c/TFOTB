"""Related diseases for one disease: every reason we hold for linking it to another disease, in one list.

Replaces the separate "clusters" view. A disease is listed once, with each reason that connects it:

- gene        same gene in HPO genes_to_disease (raw reference file; gene level, not variant level);
- family      same parent group in the MONDO hierarchy (a sibling subtype), or a parent / child form;
- mechanism   the same compartment and substance in observed claims read from papers;
- paper_link  a stored paper claim links the two diseases directly (often a hypothesis; labelled);
- ai_hypothesis  an AI hypothesis built from stored claims links them (never evidence; labelled);
- symptoms    a similar pattern of HPO-annotated symptoms (BMA-Lin, 0 to 1; similarity, not a probability).

Gene, family and symptom reasons are computed from the raw ontology files, over every annotated disease,
not over a short candidate list. Nothing here is a statement that two diseases share a cause or a treatment.
When no reason exists, `none` is true and the page says so plainly.
"""

from __future__ import annotations

from typing import Any

from atlas.clusters import mechanism_clusters
from atlas.ranking import CREDIBLE_SOURCES
from atlas.schemas import Claim, SourceType

SIMILAR_MIN = 0.4
SIMILAR_MAX = 25
SIMILAR_POOL = 80  # candidates scored for symptom similarity (pre-ordered by shared specific symptoms)
FAMILY_MAX = 40  # a parent with more children than this is too broad to call its members related
GENE_DISEASES_MAX = 40  # a gene linked to more diseases than this is listed, but each extra one is not added

ORDER = ("gene", "mechanism", "paper_link", "family", "ai_hypothesis", "symptoms")
NONE_NOTE = (
    "No similarities found in the data we hold: no shared gene in HPO genes_to_disease, no sibling in the MONDO "
    "hierarchy, no shared mechanism in the papers read, no paper or AI hypothesis linking it to another disease, "
    f"and no other disease with a symptom similarity of {SIMILAR_MIN} or more. Missing is not the same as none: "
    "the papers about it may simply not have been read yet."
)
NOTE = (
    "Each disease is listed once with every reason that links it. A reason is a lead for research, not a shared "
    "cause, a diagnosis or a treatment. Hypotheses (from a paper or from an AI) are labelled as such."
)


def _add(out: dict[str, list[dict[str, Any]]], disease: str, reason: dict[str, Any]) -> None:
    rows = out.setdefault(disease, [])
    if not any(r["kind"] == reason["kind"] and r.get("key") == reason.get("key") for r in rows):
        rows.append(reason)


def from_reference(ix: Any, entity_id: str) -> dict[str, list[dict[str, Any]]]:
    """Reasons computed from the raw reference files (HPO, MONDO) held by the search index."""
    out: dict[str, list[dict[str, Any]]] = {}
    skip = set(ix.excluded) | {entity_id}
    lab = ix.r.label_of

    # gene: the disease's own genes, else genes recorded on its subtypes (HPO often links the gene to the subtype)
    own = ix.genes_of.get(entity_id, [])
    genes = own or ix.subtype_genes(entity_id)
    for g in genes:
        others = [d for d in ix.diseases_of.get(g["id"], []) if d["id"] not in skip]
        for d in others[:GENE_DISEASES_MAX]:
            _add(out, d["id"], {
                "kind": "gene", "key": g["id"], "label": lab(g["id"]) or g["id"], "evidence": "reference",
                "claim_ids": list(dict.fromkeys(x for x in (g.get("claim_id"), d.get("claim_id")) if x)),
                "detail": f"both linked to {lab(g['id']) or g['id']} in HPO genes_to_disease"
                          + ("" if own else f" (on the subtype {lab(g['via']) or g['via']})"),
            })

    # family: siblings under the same MONDO parent (only when the parent is specific), plus direct parent / children
    for p in sorted(ix.parents.get(entity_id, ())):
        if p in ix.excluded:
            continue
        sibs = sorted(set(ix.children.get(p, ())) - skip)
        if len(sibs) <= FAMILY_MAX:
            for s in sibs:
                _add(out, s, {"kind": "family", "key": p, "label": lab(p) or p, "evidence": "reference",
                              "claim_ids": [], "detail": f"both are forms of {lab(p) or p} (MONDO hierarchy)"})
    for c in sorted(set(ix.children.get(entity_id, ())) - skip):
        _add(out, c, {"kind": "family", "key": entity_id, "label": lab(entity_id) or entity_id,
                      "evidence": "reference", "claim_ids": [], "detail": "a more specific form of this disease (MONDO)"})

    # symptoms: BMA-Lin over every disease annotated in phenotype.hpoa, best SIMILAR_MAX at or above SIMILAR_MIN
    if ix.ph is not None:
        scored = []
        for cand in ix.ph.retrieve_candidates(entity_id, {"max_candidates": SIMILAR_POOL}):
            if cand in skip:
                continue
            cmp = ix.ph.compare(entity_id, cand, {})
            if cmp.availability == "available" and cmp.score is not None and cmp.score >= SIMILAR_MIN:
                scored.append((cmp.score, cand, cmp.context_matches[:3]))
        scored.sort(key=lambda s: (-s[0], s[1]))
        for score, cand, shared in scored[:SIMILAR_MAX]:
            _add(out, cand, {"kind": "symptoms", "key": "phenotype", "label": "similar recorded symptoms",
                             "evidence": "similarity", "score": round(score, 2), "claim_ids": [],
                             "shared": [s.split(" ", 1)[1] if " " in s else s for s in shared],
                             "detail": "similar pattern of HPO-annotated symptoms (BMA-Lin, 0 to 1)"})
    return out


def from_store(entity_id: str, claims: dict[str, Claim], *, label_of=lambda _i: "") -> dict[str, list[dict[str, Any]]]:
    """Reasons from the claims read from papers and the AI hypotheses built on them."""
    out: dict[str, list[dict[str, Any]]] = {}
    for cl in mechanism_clusters(claims, label_of=label_of):
        if not any(d["id"] == entity_id for d in cl["diseases"]):
            continue
        for f in cl["shared_features"]:
            if entity_id not in f["diseases"]:
                continue
            for other in f["diseases"]:
                if other == entity_id:
                    continue
                cites = [i for i in f["claim_ids"] if {claims[i].subject_id, claims[i].object_id} & {entity_id, other}]
                _add(out, other, {"kind": "mechanism", "key": f["feature"], "label": f["label"], "evidence": "paper",
                                  "claim_ids": cites, "detail": f"observed in papers for both: {f['label']}"})
    for c in claims.values():
        ends = {c.subject_id, c.object_id}
        if entity_id not in ends or len(ends) != 2:
            continue
        other = (ends - {entity_id}).pop()
        if not other.startswith("MONDO:"):
            continue
        if c.source_type is SourceType.ai_generated:
            _add(out, other, {"kind": "ai_hypothesis", "key": c.claim_id, "label": c.predicate, "evidence": "ai_hypothesis",
                              "claim_ids": [c.claim_id], "derived_from": list(c.derived_from),
                              "detail": c.source_span.removeprefix("AI hypothesis:").strip()})
        elif c.source_type in CREDIBLE_SOURCES:
            hyp = c.status.value != "reported_observation"
            _add(out, other, {"kind": "paper_link", "key": c.claim_id, "label": c.predicate,
                              "evidence": "paper_hypothesis" if hyp else "paper", "claim_ids": [c.claim_id],
                              "detail": c.source_span})
    return out


def related_diseases(entity_id: str, *parts: dict[str, list[dict[str, Any]]], label_of=lambda _i: "",
                     hierarchy_note=lambda _a, _b: None, ai_stored: int = 0) -> dict[str, Any]:
    merged: dict[str, list[dict[str, Any]]] = {}
    for part in parts:
        for d, reasons in part.items():
            for r in reasons:
                _add(merged, d, r)
    rows = []
    for d, reasons in merged.items():
        reasons.sort(key=lambda r: ORDER.index(r["kind"]))
        kinds = {r["kind"] for r in reasons}
        sim = max((r["score"] for r in reasons if r["kind"] == "symptoms"), default=0.0)
        rows.append({"id": d, "label": label_of(d) or d, "reasons": reasons, "kinds": sorted(kinds, key=ORDER.index),
                     "hierarchy": hierarchy_note(entity_id, d), "_rank": (-len(kinds - {"family"}), -sim, label_of(d) or d)})
    rows.sort(key=lambda r: r["_rank"])
    for r in rows:
        del r["_rank"]
    counts = {k: sum(k in r["kinds"] for r in rows) for k in ORDER}
    return {"entity_id": entity_id, "diseases": rows, "total": len(rows), "counts": counts, "none": not rows,
            "note": NONE_NOTE if not rows else NOTE,
            "ai": {"stored_for_this_disease": counts["ai_hypothesis"], "stored_total": ai_stored,
                   "note": ("No AI hypothesis about this disease has been generated yet. They are built by "
                            "scripts/generate_hypotheses.py from the stored paper claims, with an AI model.")
                   if not counts["ai_hypothesis"] else
                   "AI hypotheses are proposals built from stored claims. No paper states them."}}
