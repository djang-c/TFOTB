import json

import pytest

from atlas.discovery import build_query, discover
from atlas.policy import IngestPolicy, load_policy


def fake(by_term):
    def fetch(url):
        for term, recs in by_term.items():
            if term.replace(" ", "%20") in url or term in url:
                return json.dumps({"resultList": {"result": recs}}).encode()
        return json.dumps({"resultList": {"result": []}}).encode()

    return fetch


def test_query_asks_only_for_open_access_pubmed_papers_newest_first():
    q = build_query('CLN3 "disease"')
    assert "OPEN_ACCESS:y" in q and "SRC:MED" in q and "sort_date:y" in q and "TITLE:" in q and "ABSTRACT:" in q and 'CLN3  disease' in q  # the term's own quote marks were removed


def test_discovery_dedupes_across_terms_keeps_order_and_skips_records_without_a_pmid():
    f = fake({
        "alpha": [{"pmid": "1", "title": "A"}, {"pmid": "2", "title": "B"}, {"title": "no pmid"}],
        "beta": [{"pmid": "2", "title": "B"}, {"pmid": "3", "title": "C"}],
    })
    out = discover(["alpha", "beta", "alpha", " "], fetch=f)
    assert [(x.pmid, x.query) for x in out] == [("1", "alpha"), ("2", "alpha"), ("3", "beta")]


def test_no_results_is_an_empty_list_not_an_error():
    assert discover(["nothing"], fetch=fake({})) == []


def test_missing_policy_file_means_replay_only_defaults(tmp_path):
    p = load_policy(tmp_path / "none.json")
    assert p.live_extraction is False and p.max_papers_per_run == 5


def test_policy_rejects_unknown_keys_and_silly_caps(tmp_path):
    with pytest.raises(ValueError):
        IngestPolicy.model_validate({"live_extraction": True, "typo_key": 1})
    with pytest.raises(ValueError):
        IngestPolicy.model_validate({"max_papers_per_run": 0})


def test_the_shipped_policy_file_is_valid():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    p = load_policy(root / "config" / "ingest_policy.json")
    assert p.max_papers_per_run >= 1 and p.seed_entities
