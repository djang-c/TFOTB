"""T04 -> store wiring. All inputs are SYNTHETIC."""

from atlas.extraction import ExtractedStatement, ExtractionOutput, SourceText, extract_claims
from atlas.llm.base import LLMResult
from atlas.resolver import DISEASE, GENE, Resolver
from atlas.store import PublicStore

TEXT = "SYNTHETIC. In brain samples, gene SYNA was upregulated in synthetic disease alpha."
SRC = SourceText("PMID:0000009", "https://example.org/synthetic", TEXT)


class Fake:
    provider = "fake-test"

    def __init__(self, statements):
        self.statements = statements

    def parse(self, schema, *, system, input_text, prompt_version, model_tier="fast"):
        return LLMResult(ExtractionOutput(statements=self.statements), "fake-test", "fake-model", prompt_version)


def resolver() -> Resolver:
    r = Resolver()
    r.add(DISEASE, "MONDO:0000001", "synthetic disease alpha", [])
    r.add(GENE, "HGNC:100", "SYNA", [])
    return r


def stmt(**kw):
    base = dict(
        subject_mention="synthetic disease alpha", subject_type="disease",
        object_mention="SYNA", object_type="gene", predicate="ASSOCIATED_WITH_PHENOTYPE",
        quote="gene SYNA was upregulated in synthetic disease alpha",
    )
    return ExtractedStatement(**{**base, **kw})


def test_extraction_lands_in_store_with_a_run_record():
    store = PublicStore()
    rep = extract_claims(Fake([stmt(), stmt(quote="not in the text at all")]), SRC, resolver())
    run = store.ingest_extraction(rep)
    assert len(store.claims) == 1
    assert run["claims_added"] == 1 and run["statements_quarantined"] == 1
    assert (run["provider"], run["model"], run["prompt_version"]) == ("fake-test", "fake-model", "extract-v3")
    assert store.extraction_runs == [run]
    assert "quote not found" in store.quarantine[0]["error"] and store.quarantine[0]["source_id"] == "PMID:0000009"


def test_reingesting_the_same_extraction_is_idempotent():
    store = PublicStore()
    rep = extract_claims(Fake([stmt()]), SRC, resolver())
    store.ingest_extraction(rep)
    run = store.ingest_extraction(rep)
    assert len(store.claims) == 1 and run["claims_added"] == 0 and run["claims_already_present"] == 1
    assert store.quarantine == []


def test_same_id_with_different_content_is_quarantined_not_overwritten():
    store = PublicStore()
    rep = extract_claims(Fake([stmt()]), SRC, resolver())
    store.ingest_extraction(rep)
    original = next(iter(store.claims.values()))
    altered = original.model_copy(update={"source_span": "a different span"})
    rep.claims[:] = [altered]
    store.ingest_extraction(rep)
    assert store.claims[original.claim_id].source_span == original.source_span
    assert "not overwritten" in store.quarantine[0]["error"]


def test_refused_source_is_recorded_as_not_extracted_with_no_claims():
    from atlas.extraction import ExtractionReport

    store = PublicStore()
    run = store.ingest_extraction(ExtractionReport("PMID:0000010", "not_extracted", "model refused: x"))
    assert not store.claims and run["status"] == "not_extracted" and run["claims_added"] == 0
