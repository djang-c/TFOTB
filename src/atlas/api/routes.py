"""Stub routes: every endpoint in docs/implementation/03 §4, serving the SYNTHETIC demo dataset
(data/fixtures/demo.json, built by scripts/build_demo.py) looked up by ID. Real services replace
these once T03/T04/T09 land. Every response carries the `_synthetic` label.
"""

import threading
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request

from atlas.api.claimstore import load_claims
from atlas.api.fixtures import load_fixture
from atlas.graph import find_paths, neighborhood
from atlas.policy import load_policy
from atlas.search import SearchIndex
from atlas.simulation import link_claim, run_from_report

router = APIRouter()


def _fx(request: Request, name: str) -> Any:
    return load_fixture(request.app.state.settings.fixtures_dir, name)


@lru_cache(maxsize=4)
def _demo_cached(fixtures_dir: Path) -> dict[str, Any]:
    return load_fixture(fixtures_dir, "demo")


def _demo(request: Request) -> dict[str, Any]:
    return _demo_cached(request.app.state.settings.fixtures_dir)


_index_lock = threading.Lock()


def _index_cached(raw_dir: Path) -> SearchIndex | None:
    """Built once per process; the lock stops the startup warm-up and a first request building twice."""
    with _index_lock:
        return _build_index(raw_dir)


@lru_cache(maxsize=2)
def _build_index(raw_dir: Path) -> SearchIndex | None:
    if not (raw_dir / "mondo" / "mondo.json").exists():
        return None
    return SearchIndex.from_raw(raw_dir)


def _index(request: Request) -> SearchIndex | None:
    """The real-ontology search index, or None (files not fetched, or disabled in settings)."""
    s = request.app.state.settings
    return _index_cached(s.raw_dir) if s.real_search else None


def _real_entity(request: Request, entity_id: str) -> dict[str, Any] | None:
    ix = _index(request)
    e = ix.entity(entity_id) if ix and not entity_id.startswith("SYN:") else None
    if e is None:
        return None
    versions = e.pop("version")
    source = next((v for k, v in versions.items() if k.startswith(_SOURCE_FILE[e["type"]])), None)
    return {
        **e, "identity_status": "resolved", "candidate_ids": [], "xrefs": [], "attributes": {},
        "source_url": _SOURCE_URL[e["type"]].format(id=entity_id), "source_version": source,
        "retrieved_at": "", "review_state": "unreviewed",
    }


_SOURCE_FILE = {"disease": "mondo/", "gene": "hgnc/", "phenotype": "hpo/hp.json"}
_SOURCE_URL = {
    "disease": "https://monarchinitiative.org/{id}",
    "gene": "https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{id}",
    "phenotype": "https://hpo.jax.org/browse/term/{id}",
}


REAL_NOTE = ("Not synthetic: read from pinned public files (MONDO, HGNC, HPO; versions in data/raw/CHECKSUMS.json). "
             "Unreviewed by any expert.")


DRUG_PREDICATES = frozenset({"CANDIDATE_THERAPY_FOR"})


def _stored_claims(request: Request) -> dict[str, Any]:
    s = request.app.state.settings
    hide = DRUG_PREDICATES if load_policy(s.policy_path).hide_drug_claims else frozenset()
    return load_claims(s.store_path, hide_predicates=hide)


def _label_of(request: Request) -> Any:
    ix = _index(request)
    return (lambda i: ix.r.label_of(i) or "") if ix is not None else (lambda _i: "")


STORE_NOTE = ("Not synthetic: claims extracted from papers into the local store by scripts/ingest_papers.py. "
              "Every claim is unreviewed by any expert; labels come from the pinned ontologies where available, "
              "otherwise the ID is shown.")


def _wrap(request: Request, **payload: Any) -> dict[str, Any]:
    return {"_synthetic": _demo(request)["_synthetic"], **payload}


def _wrap_real(**payload: Any) -> dict[str, Any]:
    return {"_synthetic": REAL_NOTE, **payload}


def _entity(request: Request, entity_id: str) -> dict[str, Any]:
    for e in _demo(request)["entities"]:
        if e["id"] == entity_id:
            return e
    real = _real_entity(request, entity_id)
    if real is not None:
        return real
    raise HTTPException(status_code=404, detail=f"no indexed entity {entity_id}")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta")
def meta(request: Request) -> Any:
    d = _demo(request)
    counts: dict[str, dict[str, int]] = {"source_type": {}, "review_state": {}}
    for c in d["claims"]:
        for key, tally in counts.items():
            tally[c[key]] = tally.get(c[key], 0) + 1
    by_type: dict[str, int] = {}
    for e in d["entities"]:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    return _wrap(
        request, dataset_version=d["dataset_version"], as_of=d["as_of"],
        schema_version=d["claims"][0]["schema_version"], entities_by_type=by_type,
        claims=len(d["claims"]), counts_by_source_type=counts["source_type"],
        counts_by_review_state=counts["review_state"], cached_outputs=True,
        featured=_featured(d),
        simulations=[{"run_id": k, "label": v["label"], "spec": v.get("spec"), "overall": v["report"]["overall"]}
                     for k, v in sorted(d["simulations"]["runs"].items(), key=lambda kv: kv[1]["report"]["overall"] != "pass")],
        real=_real_meta(request),
    )


# Owner decision 2026-10-03 (docs/DECISIONS.md, "Seed ID for CLN3 disease"); unreviewed by any expert.
SEED_CLUSTER = ("MONDO:0008767", "MONDO:0018982", "HGNC:2074", "HGNC:7897")


def _real_meta(request: Request) -> dict[str, Any] | None:
    """What the real-ontology layer holds, or None when the pinned files are not loaded."""
    ix = _index(request)
    if ix is None:
        return None
    seed = []
    for eid in SEED_CLUSTER:
        e = ix.entity(eid)
        if e is None:
            continue
        groups = {g["kind"]: g["total"] for g in ix.related(eid)["groups"]}
        seed.append({"id": eid, "label": e["label"], "type": e["type"], "related": groups})
    return {
        "counts": {t: sum(1 for x in ix.r._labels[t] if x not in ix.excluded) for t in ("disease", "gene", "phenotype")},
        "names": ix.size,
        "sources": ix.r.versions,
        "seed": seed,
        "seed_note": "Seed cluster chosen by the project owner on 2026-10-03; provisional and unreviewed.",
    }


def _featured(d: dict[str, Any]) -> list[dict[str, Any]]:
    """Entry points derived from what the dataset holds, never hand-picked: the entities with the
    most computed connections, then the entities with a recorded gap."""
    labels = {e["id"]: (e["label"], e["type"]) for e in d["entities"]}
    linked = sorted(d["connections"].items(), key=lambda kv: -len(kv[1]))
    out = [
        {"id": eid, "label": labels[eid][0], "type": labels[eid][1], "reason": "connections",
         "connections": len(rows), "assets": len(d["assets"].get(eid, []))}
        for eid, rows in linked if rows and eid in labels
    ][:2]
    out += [
        {"id": eid, "label": labels[eid][0], "type": labels[eid][1], "reason": "gap", "gap_kind": g["kind"]}
        for eid, g in d["gaps"].items() if eid in labels
    ][:2]
    return out[:3]


@router.get("/search")
def search(request: Request, q: str = "") -> Any:
    t = q.strip().lower()
    hits = [
        {"id": e["id"], "label": e["label"], "type": e["type"], "synonyms": e["synonyms"],
         "matched": next((s for s in e["synonyms"] if t and t in s.lower()), None)}
        for e in _demo(request)["entities"]
        if not t or t in e["label"].lower() or t in e["id"].lower()
        or any(t in s.lower() for s in e["synonyms"])
    ]
    for h in hits:
        h.update(match="demo", source_type="synthetic_fixture")
    ix = _index(request)
    if ix is None or not t:
        return _wrap(request, query=q, results=hits[:20], ambiguous=len(hits) > 1 and bool(t))
    real = ix.search(q)
    return _wrap(request, query=q, results=(real["results"] + hits)[:20],
                 ambiguous=real["ambiguous"] or (not real["results"] and len(hits) > 1))


@router.get("/entities/{entity_id}/related")
def related(request: Request, entity_id: str) -> Any:
    """What connects to an entry in the pinned ontologies and HPO files (empty for demo entries)."""
    _entity(request, entity_id)
    ix = _index(request)
    if ix is None or entity_id.startswith("SYN:"):
        return _wrap(request, entity_id=entity_id, groups=[])
    return _wrap_real(**ix.related(entity_id))


@router.get("/entities")
def entities(request: Request, type: str | None = None) -> Any:
    items = [e for e in _demo(request)["entities"] if type is None or e["type"] == type]
    return _wrap(request, items=items)


@router.get("/entities/{entity_id}")
def entity(request: Request, entity_id: str) -> Any:
    e = _entity(request, entity_id)
    d = _demo(request)
    if e.get("source_type") == "database_record" and not entity_id.startswith("SYN:"):
        ix = _index(request)
        return _wrap_real(entity=e, claims=[], claim_counts_by_predicate={}, reviewed_claims=0,
                          summary=ix.summary(entity_id) if ix else [], summary_method="template")
    claims = [c for c in d["claims"] if entity_id in (c["subject_id"], c["object_id"])]
    by_pred: dict[str, int] = {}
    for c in claims:
        by_pred[c["predicate"]] = by_pred.get(c["predicate"], 0) + 1
    return _wrap(
        request, entity=e, claims=claims, claim_counts_by_predicate=by_pred,
        reviewed_claims=sum(c["review_state"] == "reviewed" for c in claims),
        summary=d["summaries"].get(entity_id, []),
    )


@router.get("/entities/{entity_id}/connections")
def connections(request: Request, entity_id: str) -> Any:
    _entity(request, entity_id)
    ix = _index(request)
    if ix is not None and not entity_id.startswith("SYN:"):
        out = ix.connections(entity_id)
        return _wrap_real(results=out["results"], labels=out["labels"], hierarchy=out["hierarchy"], coverage=out["coverage"])
    d = _demo(request)
    results = d["connections"].get(entity_id, [])
    cov_ids = {r["coverage_manifest_id"] for r in results}
    coverage = next((m for m in d["manifests"] if m["manifest_id"] in cov_ids), None)
    return _wrap(request, results=results, coverage=coverage)


@router.get("/entities/{entity_id}/assets")
def assets(request: Request, entity_id: str) -> Any:
    _entity(request, entity_id)
    ix = _index(request)
    if ix is not None and not entity_id.startswith("SYN:"):
        out = ix.assets(entity_id)
        return _wrap_real(assets=out["assets"], coverage=out["coverage"], total=out.get("total"),
                          registry_total=out.get("registry_total"), attribution=out.get("attribution"),
                          modifications=out.get("modifications"))
    return _wrap(request, assets=_demo(request)["assets"].get(entity_id, []))


@router.get("/entities/{entity_id}/groups")
def groups(request: Request, entity_id: str) -> Any:
    """Patient groups listed by GARD (real diseases only; demo entries have none here)."""
    _entity(request, entity_id)
    ix = _index(request)
    if ix is None or entity_id.startswith("SYN:"):
        return _wrap(request, status="not_available", groups=[], pages=[])
    return _wrap_real(**ix.groups(entity_id))


@router.get("/entities/{entity_id}/collaborators")
def collaborators(request: Request, entity_id: str) -> Any:
    _entity(request, entity_id)
    return _wrap(request, items=[])


@router.get("/entities/{entity_id}/graph")
def graph(request: Request, entity_id: str, max_nodes: int = 40) -> Any:
    _entity(request, entity_id)
    ix = _index(request)
    real = ix is not None and not entity_id.startswith("SYN:")
    base = ix.graph(entity_id, max_nodes=max_nodes) if real else None
    claims = _stored_claims(request)
    if any(entity_id in (c.subject_id, c.object_id) for c in claims.values()):
        # Paper-extracted claims are added to the ontology-based graph; nothing already shown is dropped.
        extra = neighborhood(claims, entity_id, max_nodes=max(1, min(max_nodes, 200)), label_of=_label_of(request))
        g = base or {"nodes": [], "edges": [], "truncated": False, "omitted": 0}
        have = {n["id"] for n in g["nodes"]}
        nodes = g["nodes"] + [n for n in extra["nodes"] if n["id"] not in have]
        seen = {e.get("claim_id") for e in g["edges"] if e.get("claim_id")}
        edges = g["edges"] + [e for e in extra["edges"] if e["claim_id"] not in seen]
        return {"_synthetic": STORE_NOTE if not base else REAL_NOTE + " " + STORE_NOTE, "nodes": nodes, "edges": edges,
                "truncated": g["truncated"] or extra["truncated"], "omitted": g["omitted"] + extra["omitted"]}
    if base is not None:
        return _wrap_real(**base)
    g = _demo(request)["graphs"].get(entity_id, {"nodes": [], "edges": [], "truncated": False, "omitted": 0})
    return _wrap(request, **g)


@router.get("/entities/{entity_id}/routes")
def routes(request: Request, entity_id: str, to: str) -> Any:
    """Routes through stored claims between this entity and `to` (explanation only; no score)."""
    _entity(request, entity_id)
    label = _label_of(request)
    out = find_paths(_stored_claims(request), entity_id, to)
    paths = [
        {
            "nodes": [{"id": n, "label": label(n) or n} for n in p.nodes],
            "hops": [{"a": h.a, "b": h.b, "claim_ids": list(h.claim_ids), "hypothesis_only": h.hypothesis_only}
                     for h in p.hops],
            "hypothesis_only": p.hypothesis_only,
            "reviewed_claims": p.reviewed_claims,
        }
        for p in out.paths
    ]
    return {"_synthetic": STORE_NOTE, "source": entity_id, "target": to, "paths": paths,
            "gap": out.gap.model_dump(mode="json") if out.gap else None}


@router.get("/entities/{entity_id}/gap")
def gap(request: Request, entity_id: str) -> Any:
    _entity(request, entity_id)
    ix = _index(request)
    if ix is not None and not entity_id.startswith("SYN:"):
        out = ix.connections(entity_id)
        return _wrap_real(gap=out["gap"], coverage=out["coverage"] if out["gap"] else None)
    d = _demo(request)
    g = d["gaps"].get(entity_id)
    coverage = None
    if g:
        coverage = next(m for m in d["manifests"] if m["manifest_id"] == g["coverage_manifest_id"])
    return _wrap(request, gap=g, coverage=coverage)


@router.get("/entities/{entity_id}/actions")
def entity_actions(request: Request, entity_id: str) -> Any:
    _entity(request, entity_id)
    ix = _index(request)
    if ix is not None and not entity_id.startswith("SYN:"):
        return _wrap_real(cards=ix.actions(entity_id))
    return _wrap(request, cards=_demo(request)["cards"].get(entity_id, []))


@router.get("/claims/{claim_id}")
def claim(request: Request, claim_id: str) -> Any:
    ix = _index(request)
    real = ix.claim(claim_id) if ix is not None else None
    if real is not None:
        subject = ix.r.label_of(real["subject_id"]) or real["context"].get("study_title") or real["subject_id"]
        return _wrap_real(claim=real, subject_label=subject,
                          object_label=ix.r.label_of(real["object_id"]), lineage_siblings=[], contradicting_claims=[])
    stored = _stored_claims(request).get(claim_id)
    if stored is not None:
        lab = _label_of(request)
        return {"_synthetic": STORE_NOTE, "claim": stored.model_dump(mode="json"),
                "subject_label": lab(stored.subject_id) or stored.subject_id,
                "object_label": lab(stored.object_id) or stored.object_id,
                "lineage_siblings": [], "contradicting_claims": []}
    d = _demo(request)
    c = next((c for c in d["claims"] if c["claim_id"] == claim_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail=f"no claim {claim_id}")
    labels = {e["id"]: e["label"] for e in d["entities"]}
    siblings = [x["claim_id"] for x in d["claims"]
                if x["lineage_id"] == c["lineage_id"] and x["claim_id"] != claim_id]
    contradicting = [x["claim_id"] for x in d["claims"]
                     if claim_id in x["contradicts"] or x["claim_id"] in c["contradicts"]]
    return _wrap(
        request, claim=c, subject_label=labels.get(c["subject_id"]),
        object_label=labels.get(c["object_id"]), lineage_siblings=siblings,
        contradicting_claims=contradicting,
    )


@router.post("/explain")
def explain(request: Request, body: Annotated[dict[str, Any] | None, Body()] = None) -> Any:
    sentences = _demo(request)["summaries"].get((body or {}).get("entity_id", ""), [])
    return _wrap(request, sentences=sentences, dropped=0, cached=True)


@router.post("/actions")
def actions(request: Request, body: Annotated[dict[str, Any] | None, Body()] = None) -> Any:
    return _wrap(request, cards=_demo(request)["cards"].get((body or {}).get("entity_id", ""), []))


@router.post("/uploads")
def uploads(request: Request) -> Any:
    return _fx(request, "upload")


@router.get("/simulations/{run_id}")
def simulation(request: Request, run_id: str) -> Any:
    sims = _demo(request)["simulations"]
    run = sims["runs"].get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no simulation {run_id}")
    # T23 graph link (atlas.simulation): one SIMULATES_WORKFLOW_FOR claim to the demo entry whose action
    # card reports this workflow. Computer prediction, unreviewed, never biological support. Runs stay
    # attached to the demo only: the specs are generic illustrations, not a protocol for a real disease.
    d = _demo(request)
    entity = next((eid for eid, cards in d["cards"].items() for c in cards if c["kind"] == "simulation_report"), None)
    link, linked = None, None
    if entity:
        rec = run_from_report(run["report"])
        link = link_claim(rec, entity).model_dump(mode="json")
        linked = {"id": entity, "label": next((e["label"] for e in d["entities"] if e["id"] == entity), entity)}
    return _wrap(request, scene=sims["scene"], **run, graph_link=link, linked_entity=linked)
