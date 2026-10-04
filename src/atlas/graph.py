"""T05/T09 graph projection: a NetworkX view of stored claims, for the optional canvas and for paths.

Rules:
- Every edge is one claim and carries its `claim_id`; nothing here creates an edge.
- A hop counts as evidence only if one of its claims is a reported observation (`ranking.is_evidential`): an AI
  hypothesis, an inference, a prediction or a simulation record never makes a hop "supported".
- Paths are for explanation only. Each hop lists the claims that support it. A hop supported only by
  `inference` claims makes the whole path "hypothesis only". A missing arrow is never filled: if no
  route exists the caller gets a scoped `GapResult` (kind `no_supported_route`), never a guess.
- No path score. Paths are ordered: not hypothesis-only first, then fewer hops, then more reviewed
  claims, then IDs. Direction of a claim is kept on the edge but paths may cross it, because a
  disease-gene-disease route reads the same edge both ways.
- Neighbourhood size is capped; what is left out is counted (`truncated`, `omitted`), never hidden.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import islice, pairwise
from typing import Any

import networkx as nx

from atlas.ranking import is_evidential
from atlas.schemas import Claim, ClaimStatus, GapResult, ReviewState

MAX_HOPS = 4
DEFAULT_K = 3
REVIEWER_ROLE = "domain expert (unassigned; claims are unreviewed)"


_NODE_TYPE = {"MONDO": "disease", "HGNC": "gene", "HP": "phenotype", "GO": "compartment", "CHEBI": "chemical"}


def node_type(entity_id: str) -> str:
    return _NODE_TYPE.get(entity_id.partition(":")[0], "other")


def build_graph(claims: dict[str, Claim]) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for cid in sorted(claims):
        c = claims[cid]
        g.add_edge(
            c.subject_id, c.object_id, key=cid, claim_id=cid, predicate=c.predicate,
            status=c.status.value, review_state=c.review_state.value,
        )
    return g


@dataclass(frozen=True)
class Hop:
    a: str
    b: str
    claim_ids: tuple[str, ...]
    hypothesis_only: bool  # every claim on this hop is an inference


@dataclass(frozen=True)
class PathResult:
    nodes: tuple[str, ...]
    hops: tuple[Hop, ...]
    hypothesis_only: bool  # at least one hop has no observed, credible claim behind it
    reviewed_claims: int
    # Intermediate stops that are shared cell compartments or chemicals (GO / ChEBI). Such a stop is a shared
    # feature, not a mechanism link: "both diseases store material in the lysosome" does not tie their genes together.
    shared_feature_stops: tuple[str, ...] = ()

    @property
    def claim_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(i for h in self.hops for i in h.claim_ids))


@dataclass(frozen=True)
class PathOutcome:
    source: str
    target: str
    paths: tuple[PathResult, ...]
    gap: GapResult | None  # set only when no path exists


def _simple(g: nx.MultiDiGraph) -> nx.Graph:
    s = nx.Graph()
    for a, b in g.edges():
        if a != b:
            s.add_edge(a, b)
    return s


def _hop_claims(g: nx.MultiDiGraph, a: str, b: str) -> list[str]:
    ids = []
    for u, v in ((a, b), (b, a)):
        if g.has_edge(u, v):
            ids += [d["claim_id"] for d in g[u][v].values()]
    return sorted(set(ids))


def find_paths(
    claims: dict[str, Claim], source: str, target: str, *, k: int = DEFAULT_K, max_hops: int = MAX_HOPS,
    coverage_manifest_id: str = "COV:none", as_of: date | None = None, graph: nx.MultiDiGraph | None = None,
) -> PathOutcome:
    g = graph if graph is not None else build_graph(claims)  # callers that ask many pairs build it once
    s = _simple(g)
    found: list[PathResult] = []
    if source in s and target in s and source != target:
        # take more than k shortest so that the preference order below can pick the best k
        try:
            candidates = list(islice(nx.shortest_simple_paths(s, source, target), 50))
        except nx.NetworkXNoPath:  # the entities sit in different parts of the graph
            candidates = []
        for nodes in candidates:
            if len(nodes) - 1 > max_hops:
                break
            hops = []
            for a, b in pairwise(nodes):
                ids = _hop_claims(g, a, b)
                no_evidence = not any(is_evidential(claims[i]) and claims[i].status is ClaimStatus.reported_observation for i in ids)
                hops.append(Hop(a, b, tuple(ids), no_evidence))
            reviewed = sum(
                1 for h in hops for i in h.claim_ids if claims[i].review_state is ReviewState.reviewed
            )
            stops = tuple(n for n in nodes[1:-1] if node_type(n) in {"compartment", "chemical"})
            found.append(PathResult(tuple(nodes), tuple(hops), any(h.hypothesis_only for h in hops), reviewed, stops))
    found.sort(key=lambda p: (p.hypothesis_only, len(p.hops), -p.reviewed_claims, p.nodes))
    paths = tuple(found[:k])
    gap = None
    if not paths:
        day = as_of or datetime.now(UTC).date()
        gap = GapResult(
            kind="no_supported_route",
            statement=(
                f"No supported route of up to {max_hops} steps found between these two entities in the "
                f"indexed evidence as of {day.isoformat()}."
            ),
            as_of=day,
            entity_id=source,
            coverage_manifest_id=coverage_manifest_id,
            missing_information=("a stored claim linking the two entities, directly or through another entity",),
            reviewer_role=REVIEWER_ROLE,
        )
    return PathOutcome(source, target, paths, gap)


def neighborhood(
    claims: dict[str, Claim], entity_id: str, *, max_nodes: int = 40, label_of: Callable[[str], str] = lambda _i: "",
) -> dict[str, Any]:
    """Nodes and claim edges around an entity for the optional canvas, capped at `max_nodes`."""
    if max_nodes < 1:
        raise ValueError("max_nodes must be at least 1")
    g = build_graph(claims)
    s = _simple(g)
    if entity_id not in s:
        return {"nodes": [], "edges": [], "truncated": False, "omitted": 0}

    def weight(n: str) -> tuple:
        ids = [i for u in s[n] for i in _hop_claims(g, n, u)]
        reviewed = sum(1 for i in ids if claims[i].review_state is ReviewState.reviewed)
        return (-reviewed, -len(ids), n)

    ring1 = sorted(s[entity_id], key=weight)
    ring2 = sorted({m for n in ring1 for m in s[n]} - set(ring1) - {entity_id}, key=weight)
    reachable = [entity_id, *ring1, *ring2]
    keep = reachable[:max_nodes]
    kept = set(keep)
    edges = [
        {"source": c.subject_id, "target": c.object_id, "claim_id": cid, "predicate": c.predicate,
         "status": c.status.value, "review_state": c.review_state.value}
        for cid, c in sorted(claims.items())
        if c.subject_id in kept and c.object_id in kept
    ]
    nodes = [{"id": n, "label": label_of(n) or n, "type": node_type(n), "is_query": n == entity_id} for n in keep]
    omitted = len(reachable) - len(keep)
    return {"nodes": nodes, "edges": edges, "truncated": omitted > 0, "omitted": omitted}
