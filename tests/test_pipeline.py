"""Pipeline tests with a fake paper source and a fake model (SYNTHETIC; software behaviour only)."""

import pytest

from atlas.db import AtlasDB
from atlas.extraction import ExtractedStatement, ExtractionOutput
from atlas.llm.base import LLMResult
from atlas.pipeline import ingest_papers
from atlas.resolver import DISEASE, GENE, Resolver
from atlas.schemas import Claim, SourceStatus
from atlas.sources import FullText, SourceError

QUOTE = "gene SYNA is linked to synthetic disease alpha"
TEXT = f"SYNTHETIC TEXT. We report that {QUOTE} in this cohort."


class Fake:
    provider = "fake"

    def __init__(self, statements=None):
        self.calls = 0
        self.statements = statements if statements is not None else [
            ExtractedStatement(
                subject_mention="SYNA", subject_type="gene", object_mention="synthetic disease alpha",
                object_type="disease", predicate="GENE_ASSOCIATED_WITH_DISEASE", quote=QUOTE,
            ),
            ExtractedStatement(  # the quote is not in the text, so it must be quarantined
                subject_mention="SYNA", subject_type="gene", object_mention="synthetic disease alpha",
                object_type="disease", predicate="GENE_ASSOCIATED_WITH_DISEASE", quote="invented sentence",
            ),
        ]

    def parse(self, schema, **kw):
        self.calls += 1
        return LLMResult(ExtractionOutput(statements=self.statements), "fake", "fake-model", kw["prompt_version"])


@pytest.fixture()
def resolver():
    r = Resolver()
    r.add(DISEASE, "MONDO:0000001", "synthetic disease alpha", [])
    r.add(GENE, "HGNC:100", "SYNA", [])
    return r


def paper(pmid, licence="cc by", text=TEXT):
    return FullText(pmid, f"PMC{pmid}", "t", licence, text, "https://example.invalid/x", doi="10.1000/x", journal="Synthetic Journal")


def source(**by_pmid):
    def fetch(pmid):
        item = by_pmid[pmid]
        if isinstance(item, Exception):
            raise item
        return item

    return fetch


def run(pmids, resolver, db, client=None, **kw):
    kw.setdefault("fetch", source(**{p: paper(p) for p in pmids}))
    return ingest_papers(pmids, client=client or Fake(), resolver=resolver, db=db, **kw)


def test_good_paper_stores_unreviewed_claims_and_quarantines_the_invented_quote(resolver):
    db = AtlasDB()
    rep = run(["1"], resolver, db)
    r = rep.runs[0]
    assert (r.status, r.claims_added, r.statements_quarantined) == ("ingested", 1, 1)
    claim = db.all(Claim)[0]
    assert claim.review_state.value == "unreviewed" and claim.claim_id.startswith("CLAIM:PMID-1-")
    assert "invented sentence" in str(db.quarantined()[0]["payload"])


def test_rerunning_the_same_paper_adds_nothing_and_never_overwrites(resolver):
    db = AtlasDB()
    run(["1"], resolver, db)
    r = run(["1"], resolver, db).runs[0]
    assert (r.claims_added, r.claims_already_present) == (0, 1) and len(db.all(Claim)) == 1


def test_any_licence_is_accepted_by_default_and_recorded_but_a_restriction_can_be_set(resolver):
    nc = {"1": paper("1", "cc by-nc-nd")}
    client = Fake()
    rep = run(["1"], resolver, AtlasDB(), client, fetch=source(**nc))
    assert rep.runs[0].status == "ingested" and rep.runs[0].licence == "cc by-nc-nd"
    blocked = run(["1"], resolver, AtlasDB(), client, fetch=source(**nc), allowed_licences=["cc by"])
    assert blocked.runs[0].status == "skipped" and "allow-list" in blocked.runs[0].reason and client.calls == 1


def test_the_per_run_cap_skips_the_rest_with_a_reason(resolver):
    client = Fake()
    rep = run(["1", "2", "3"], resolver, AtlasDB(), client, max_papers=2)
    assert [r.status for r in rep.runs] == ["ingested", "ingested", "skipped"]
    assert "cap of 2" in rep.runs[2].reason and client.calls == 2


def test_oversize_text_and_unavailable_papers_are_skipped_or_failed_not_dropped(resolver):
    fetch = source(**{"1": paper("1", text="x" * 50), "2": SourceError("not open access")})
    rep = run(["1", "2"], resolver, AtlasDB(), fetch=fetch, max_chars=10)
    assert [r.status for r in rep.runs] == ["skipped", "failed"] and "not open access" in rep.runs[1].reason


def test_already_done_sources_are_skipped_without_a_model_call(resolver):
    client = Fake()
    rep = run(["1"], resolver, AtlasDB(), client, skip=["PMID:1"])
    assert rep.runs == [] and client.calls == 0


def test_coverage_marks_skipped_and_failed_sources_as_failed_never_as_zero(resolver):
    fetch = source(**{"1": paper("1"), "2": SourceError("not open access")})
    cov = run(["1", "2"], resolver, AtlasDB(), fetch=fetch).coverage()
    assert [(c.source, c.status) for c in cov] == [("PMID:1", SourceStatus.ok), ("PMID:2", SourceStatus.failed)]
    assert cov[0].fetched == 2 and cov[0].screened == 1 and cov[1].fetched is None


def test_a_changed_claim_with_the_same_id_is_quarantined_not_overwritten(resolver):
    db = AtlasDB()
    run(["1"], resolver, db)
    stored = db.all(Claim)[0]
    from atlas import pipeline

    changed = stored.model_copy(update={"source_span": "different text"})
    assert pipeline._store_claim(db, changed, "PMID:1") == "conflict"
    assert db.all(Claim)[0] == stored and "not overwritten" in db.quarantined()[-1]["error"]


def test_claims_cite_the_papers_real_doi_link_and_the_run_log_records_journal(resolver):
    db = AtlasDB()
    r = run(["1"], resolver, db).runs[0]
    assert r.citation == "https://doi.org/10.1000/x" and r.journal == "Synthetic Journal"
    assert db.all(Claim)[0].source_url == "https://doi.org/10.1000/x"


def test_a_network_error_on_one_paper_fails_that_paper_only_and_the_run_continues(resolver):
    import urllib.error

    def fetch(pmid):
        if pmid == "1":
            raise urllib.error.URLError("timed out")
        return paper(pmid)

    rep = run(["1", "2"], resolver, AtlasDB(), fetch=fetch)
    assert [r.status for r in rep.runs] == ["failed", "ingested"] and "timed out" in rep.runs[0].reason


def test_a_missing_recorded_response_fails_that_paper_only_and_the_run_continues(resolver):
    from atlas.llm.base import LLMError

    class Flaky(Fake):
        def parse(self, schema, **kw):
            if self.calls == 0:
                self.calls += 1
                raise LLMError("replay cache miss; no live call made")
            return super().parse(schema, **kw)

    rep = run(["1", "2"], resolver, AtlasDB(), Flaky())
    assert [r.status for r in rep.runs] == ["failed", "ingested"] and "replay cache miss" in rep.runs[0].reason


def test_the_publication_date_comes_from_the_record_and_a_bad_date_is_left_unknown(resolver):
    from dataclasses import replace

    db = AtlasDB()
    run(["1"], resolver, db, fetch=source(**{"1": replace(paper("1"), published="2023-05-26")}))
    assert db.all(Claim)[0].published_at.isoformat() == "2023-05-26"
    db2 = AtlasDB()
    run(["2"], resolver, db2, fetch=source(**{"2": replace(paper("2"), published="not a date")}))
    assert db2.all(Claim)[0].published_at is None
