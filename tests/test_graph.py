"""Graph projection tests. Claims are SYNTHETIC fixtures (software behaviour only)."""

from datetime import date
from itertools import pairwise

import pytest
from tests.conftest import make_claim

from atlas.graph import build_graph, find_paths, neighborhood

D1, G1, D2, D3 = "MONDO:0000001", "HGNC:1", "MONDO:0000002", "MONDO:0000003"


def claims(*specs):
    out = {}
    for cid, s, o, kw in specs:
        out[cid] = make_claim(cid, kw.pop("pred", "GENE_ASSOCIATED_WITH_DISEASE"), subject_id=s, object_id=o, **kw)
    return out


def test_every_edge_carries_its_claim_id_and_nothing_else_creates_edges():
    cs = claims(("CLAIM:a", G1, D1, {}), ("CLAIM:b", G1, D2, {}))
    g = build_graph(cs)
    assert {d["claim_id"] for _, _, d in g.edges(data=True)} == set(cs) and g.number_of_edges() == 2


def test_path_through_a_shared_gene_lists_the_claim_on_every_hop():
    cs = claims(("CLAIM:a", G1, D1, {}), ("CLAIM:b", G1, D2, {}))
    out = find_paths(cs, D1, D2)
    assert out.gap is None and out.paths[0].nodes == (D1, G1, D2)
    assert [h.claim_ids for h in out.paths[0].hops] == [("CLAIM:a",), ("CLAIM:b",)]
    assert not out.paths[0].hypothesis_only


def test_a_hop_supported_only_by_inference_makes_the_path_hypothesis_only():
    cs = claims(("CLAIM:a", D1, D2, {"pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference"}))
    p = find_paths(cs, D1, D2).paths[0]
    assert p.hypothesis_only and p.hops[0].hypothesis_only


def test_a_hop_with_one_observed_claim_is_not_hypothesis_only():
    cs = claims(
        ("CLAIM:a", D1, D2, {"pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference"}),
        ("CLAIM:b", D1, D2, {"pred": "PERTURBS_MECHANISM"}),
    )
    assert not find_paths(cs, D1, D2).paths[0].hypothesis_only


def test_no_route_returns_a_scoped_gap_and_never_a_made_up_arrow():
    cs = claims(("CLAIM:a", G1, D1, {}), ("CLAIM:b", "HGNC:2", D2, {}))
    out = find_paths(cs, D1, D2, as_of=date(2026, 10, 3))
    assert out.paths == () and out.gap.kind == "no_supported_route"
    assert "indexed evidence as of 2026-10-03" in out.gap.statement


def test_unknown_entity_is_a_gap_not_an_error():
    assert find_paths({}, D1, D2).gap is not None


def test_routes_longer_than_the_hop_limit_are_not_returned():
    chain = [D1, "HGNC:1", "MONDO:0000009", "HGNC:2", "MONDO:0000010", D2]  # 5 hops
    cs = claims(*((f"CLAIM:{i}", a, b, {}) for i, (a, b) in enumerate(pairwise(chain))))
    assert find_paths(cs, D1, D2, max_hops=4).gap is not None
    assert find_paths(cs, D1, D2, max_hops=5).paths


def test_observed_paths_come_before_hypothesis_only_ones_even_when_longer_and_k_is_respected():
    cs = claims(
        ("CLAIM:direct", D1, D2, {"pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference"}),
        ("CLAIM:a", G1, D1, {}), ("CLAIM:b", G1, D2, {}),
    )
    both = find_paths(cs, D1, D2)
    assert [p.hypothesis_only for p in both.paths] == [False, True]
    one = find_paths(cs, D1, D2, k=1)
    assert len(one.paths) == 1 and one.paths[0].nodes == (D1, G1, D2)


def test_neighbourhood_never_exceeds_max_nodes_and_omissions_add_up():
    cs = claims(*((f"CLAIM:{i}", G1, f"MONDO:{i + 10:07d}", {}) for i in range(30)), ("CLAIM:q", G1, D1, {}))
    for cap in (1, 5, 40):
        n = neighborhood(cs, G1, max_nodes=cap)
        total = 32  # the gene plus 31 diseases
        assert len(n["nodes"]) == min(cap, total) and n["omitted"] == total - len(n["nodes"])
        assert n["truncated"] is (n["omitted"] > 0)
        ids = {x["id"] for x in n["nodes"]}
        assert all(e["source"] in ids and e["target"] in ids for e in n["edges"])


def test_neighbourhood_keeps_the_query_and_prefers_reviewed_neighbours():
    cs = claims(("CLAIM:a", G1, D1, {}), ("CLAIM:r", G1, D2, {"review_state": "reviewed"}), ("CLAIM:c", G1, D3, {}))
    n = neighborhood(cs, G1, max_nodes=2)
    assert [x["id"] for x in n["nodes"]] == [G1, D2] and n["nodes"][0]["is_query"]


def test_neighbourhood_of_an_unknown_entity_is_empty_not_an_error():
    assert neighborhood({}, D1) == {"nodes": [], "edges": [], "truncated": False, "omitted": 0}
    with pytest.raises(ValueError):
        neighborhood({}, D1, max_nodes=0)


def test_a_hop_backed_only_by_an_ai_hypothesis_a_prediction_or_a_simulation_is_not_supported_evidence():
    from atlas.simulation import link_claim, run_from_report

    for kw in (
        {"pred": "ASSOCIATED_WITH_PHENOTYPE", "status": "computational_prediction"},
        {"pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference", "source_type": "ai_generated"},
    ):
        cs = claims(("CLAIM:a", D1, D2, kw))
        assert find_paths(cs, D1, D2).paths[0].hypothesis_only, kw
    # an observed claim next to an AI claim on the same hop is enough support for that hop
    cs = claims(("CLAIM:a", D1, D2, {"pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference", "source_type": "ai_generated"}),
                ("CLAIM:b", D1, D2, {"source_type": "published"}))
    assert not find_paths(cs, D1, D2).paths[0].hypothesis_only
    assert run_from_report and link_claim  # simulation records are excluded by `is_evidential` (covered in test_ranking)


def test_a_route_through_a_shared_compartment_is_flagged_as_a_shared_feature_not_a_mechanism():
    cs = claims(
        ("CLAIM:a", D1, "GO:0005764", {"pred": "ACCUMULATES_IN_COMPARTMENT"}),
        ("CLAIM:b", D2, "GO:0005764", {"pred": "ACCUMULATES_IN_COMPARTMENT"}),
    )
    p = find_paths(cs, D1, D2).paths[0]
    assert p.shared_feature_stops == ("GO:0005764",)
    via_gene = find_paths(claims(("CLAIM:a", G1, D1, {}), ("CLAIM:b", G1, D2, {})), D1, D2).paths[0]
    assert via_gene.shared_feature_stops == ()  # a shared gene is not a generic hub


def test_a_prebuilt_graph_gives_the_same_paths():
    cs = claims(("CLAIM:a", G1, D1, {}), ("CLAIM:b", G1, D2, {}))
    assert find_paths(cs, D1, D2, graph=build_graph(cs)) == find_paths(cs, D1, D2)
