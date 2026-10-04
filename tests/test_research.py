"""run_research end to end with a fake paper source, fake discovery and a fake model (SYNTHETIC)."""

import json

from atlas.discovery import Found
from atlas.extraction import ExtractedStatement, ExtractionOutput
from atlas.llm.base import LLMResult
from atlas.policy import IngestPolicy
from atlas.research import already_ingested, live_allowed, run_research
from atlas.resolver import DISEASE, GENE, Resolver
from atlas.sources import FullText

QUOTE = "gene SYNA is linked to synthetic disease alpha"
TEXT = f"SYNTHETIC TEXT. We report that {QUOTE} in this cohort."


class Fake:
    provider = "fake"

    def __init__(self):
        self.calls = 0

    def parse(self, schema, **kw):
        self.calls += 1
        st = ExtractedStatement(
            subject_mention="SYNA", subject_type="gene", object_mention="synthetic disease alpha", object_type="disease",
            predicate="GENE_ASSOCIATED_WITH_DISEASE", quote=QUOTE,
        )
        return LLMResult(ExtractionOutput(statements=[st]), "fake", "fake-model", kw["prompt_version"])


def resolver():
    r = Resolver()
    r.add(DISEASE, "MONDO:0000001", "synthetic disease alpha", [])
    r.add(GENE, "HGNC:100", "SYNA", [])
    return r


def paper(pmid):
    return FullText(pmid, f"PMC{pmid}", "t", "cc by", TEXT, "https://example.invalid/x", doi=f"10.1000/{pmid}", journal="J")


def go(tmp_path, found, client=None, **policy):
    client = client or Fake()
    summary = run_research(
        terms=["alpha"], pmids=None, policy=IngestPolicy(**policy), store_dir=tmp_path / "store", client=client,
        resolver=resolver(), live=False, discover_fn=lambda terms, per_query: found, fetch=paper,
    )
    return summary, client


def test_a_run_discovers_ingests_logs_and_snapshots(tmp_path):
    s, client = go(tmp_path, [Found("1", "A", "alpha"), Found("2", "B", "alpha")])
    assert (s["discovered"], s["new_papers"], s["claims_added"], client.calls) == (2, 2, 2, 2)
    assert s["snapshot_rows"]["claims.jsonl"] == 2
    log = [json.loads(x) for x in (tmp_path / "store" / "ingest_log.jsonl").read_text().splitlines()]
    assert {r["source_id"] for r in log} == {"PMID:1", "PMID:2"} and all(r["citation"].startswith("https://doi.org/") for r in log)


def test_a_second_run_skips_papers_already_ingested_so_nothing_is_paid_for_twice(tmp_path):
    go(tmp_path, [Found("1", "A", "alpha")])
    s, client = go(tmp_path, [Found("1", "A", "alpha")])
    assert s["new_papers"] == 0 and client.calls == 0 and already_ingested(tmp_path / "store") == {"PMID:1"}


def test_the_policy_cap_limits_papers_per_run_and_the_rest_are_reported_as_skipped(tmp_path):
    s, client = go(tmp_path, [Found(str(i), "t", "alpha") for i in range(1, 5)], max_papers_per_run=2)
    assert client.calls == 2
    assert [p["status"] for p in s["papers"]] == ["ingested", "ingested", "skipped", "skipped"]


def test_live_calls_need_both_the_policy_and_a_key(monkeypatch):
    on = IngestPolicy(live_extraction=True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert live_allowed(on) is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert live_allowed(on) is True and live_allowed(IngestPolicy()) is False and live_allowed(on, offline=True) is False
