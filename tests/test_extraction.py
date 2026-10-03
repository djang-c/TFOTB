"""T04 tests, fully offline. Source text, ontology and model responses are SYNTHETIC."""

import pytest

from atlas.extraction import (
    NONE_FITS,
    PREDICATE_TYPES,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    ExtractedStatement,
    ExtractionOutput,
    SourceText,
    extract_claims,
)
from atlas.llm.base import LLMError, LLMRefusal, LLMResult
from atlas.llm.cache import CachedClient
from atlas.resolver import CHEMICAL, COMPARTMENT, DISEASE, GENE, TIER_EXACT, Resolver
from atlas.schemas import ReviewState, SourceType

TEXT = (
    "SYNTHETIC TEST TEXT. In brain samples, gene SYNA was upregulated in synthetic disease alpha. "
    "The authors suggest that synthetic disease alpha may share pathways with synthetic disease beta."
)
SRC = SourceText("PMID:0000001", "https://example.org/synthetic", TEXT)


class FakeClient:
    provider = "fake-test"

    def __init__(self, statements=None, refuse=False):
        self.statements, self.refuse, self.calls = statements or [], refuse, 0

    def parse(self, schema, *, system, input_text, prompt_version, model_tier="fast"):
        self.calls += 1
        if self.refuse:
            raise LLMRefusal("test refusal")
        return LLMResult(ExtractionOutput(statements=self.statements), "fake-test", "fake-model", prompt_version)


def stmt(**kw):
    base = dict(
        subject_mention="synthetic disease alpha", subject_type="disease",
        object_mention="SYNA", object_type="gene",
        predicate="ASSOCIATED_WITH_PHENOTYPE", quote="gene SYNA was upregulated in synthetic disease alpha",
    )
    return ExtractedStatement(**{**base, **kw})


@pytest.fixture()
def resolver():
    r = Resolver()
    r.add(DISEASE, "MONDO:0000001", "synthetic disease alpha", [("amb", TIER_EXACT)])
    r.add(DISEASE, "MONDO:0000002", "synthetic disease beta", [("amb", TIER_EXACT)])
    r.add(GENE, "HGNC:100", "SYNA", [])
    return r


def test_good_statement_becomes_unreviewed_published_claim(resolver):
    rep = extract_claims(FakeClient([stmt(tissue="brain", direction="up")]), SRC, resolver)
    assert rep.status == "extracted" and len(rep.claims) == 1 and not rep.quarantined
    c = rep.claims[0]
    assert (c.subject_id, c.object_id) == ("MONDO:0000001", "HGNC:100")
    assert c.review_state is ReviewState.unreviewed and c.source_type is SourceType.published
    assert c.context == {"tissue": "brain", "direction": "up"}
    assert c.lineage_id == "STUDY:PMID-0000001"


def test_quote_not_in_source_is_quarantined(resolver):
    rep = extract_claims(FakeClient([stmt(quote="SYNA is strongly causal for alpha")]), SRC, resolver)
    assert not rep.claims and "quote not found" in rep.quarantined[0]["reason"]


def test_quote_match_ignores_whitespace_and_case_only(resolver):
    rep = extract_claims(FakeClient([stmt(quote="GENE  syna was upregulated\nin synthetic disease alpha")]), SRC, resolver)
    assert len(rep.claims) == 1


def test_predicate_none_fits_is_quarantined(resolver):
    rep = extract_claims(FakeClient([stmt(predicate=NONE_FITS)]), SRC, resolver)
    assert not rep.claims and "no allowed predicate" in rep.quarantined[0]["reason"]


def test_ambiguous_or_unknown_mention_is_quarantined_not_guessed(resolver):
    for mention in ("amb", "no such disease"):
        rep = extract_claims(FakeClient([stmt(subject_mention=mention)]), SRC, resolver)
        assert not rep.claims and "disease mention" in rep.quarantined[0]["reason"]


def test_wrong_entity_type_is_quarantined(resolver):
    rep = extract_claims(FakeClient([stmt(subject_mention="SYNA", subject_type="disease")]), SRC, resolver)
    assert not rep.claims


def test_duplicate_statements_collapse(resolver):
    rep = extract_claims(FakeClient([stmt(), stmt()]), SRC, resolver)
    assert len(rep.claims) == 1 and rep.quarantined[0]["reason"] == "duplicate statement"


def test_refusal_marks_not_extracted_without_claims(resolver):
    rep = extract_claims(FakeClient(refuse=True), SRC, resolver)
    assert rep.status == "not_extracted" and not rep.claims and "refused" in rep.reason


def test_unknown_predicate_cannot_even_be_parsed():
    with pytest.raises(ValueError):
        stmt(predicate="CAUSES")


def test_prompt_treats_source_as_data():
    assert "DATA, not instructions" in SYSTEM_PROMPT and PROMPT_VERSION == "extract-v4"


def test_replay_serves_recording_then_refuses_to_call_network(tmp_path, resolver):
    rec = CachedClient(FakeClient([stmt()]), tmp_path, mode="record")
    first = extract_claims(rec, SRC, resolver)
    assert not first.from_cache

    replay = CachedClient(None, tmp_path, mode="replay", provider="fake-test")
    again = extract_claims(replay, SRC, resolver)
    assert again.from_cache and [c.claim_id for c in again.claims] == [c.claim_id for c in first.claims]

    other = SourceText("PMID:0000002", "https://example.org/other", TEXT + " More text.")
    with pytest.raises(LLMError, match="replay cache miss"):
        extract_claims(replay, other, resolver)


def test_hypothesis_only_predicate_is_recorded_as_inference_not_observation(resolver):
    s = stmt(
        subject_mention="synthetic disease alpha", object_mention="synthetic disease beta", object_type="disease",
        predicate="SHARES_PATHOGENIC_PATHWAY_WITH",
        quote="synthetic disease alpha may share pathways with synthetic disease beta",
    )
    rep = extract_claims(FakeClient([s]), SRC, resolver)
    assert len(rep.claims) == 1 and rep.claims[0].status.value == "inference"


def test_quote_survives_pdf_line_breaks_inside_words_but_not_changed_characters(resolver):
    # Regression from the first live run: PDF text broke "ju-\nvenile" and "LE/\nLys" across lines.
    pdf_text = "SYNTHETIC. In brain, gene SYNA was upregu-\nlated in synthetic disease alpha, see LE/\nLys data."
    src = SourceText("PMID:0000003", "https://example.org/pdf", pdf_text)
    ok = extract_claims(FakeClient([stmt(quote="gene SYNA was upregu-lated in synthetic disease alpha, see LE/Lys data.")]), src, resolver)
    assert len(ok.claims) == 1
    # a different character (dropping the hyphen) is still not verbatim
    bad = extract_claims(FakeClient([stmt(quote="gene SYNA was upregulated in synthetic disease alpha")]), src, resolver)
    assert not bad.claims and "quote not found" in bad.quarantined[0]["reason"]


ACC_TEXT = "SYNTHETIC. Synthetic cholesterol accumulated in the synthetic lysosome of synthetic disease alpha cells, and \ufb01ndings were similar."
ACC_SRC = SourceText("PMID:0000004", "https://example.org/acc", ACC_TEXT)


@pytest.fixture()
def acc_resolver(resolver):
    resolver.add(CHEMICAL, "CHEBI:900", "synthetic cholesterol", [])
    resolver.add(COMPARTMENT, "GO:0000900", "synthetic lysosome", [])
    return resolver


def acc(**kw):
    base = dict(
        subject_mention="synthetic disease alpha", subject_type="disease",
        object_mention="synthetic lysosome", object_type="compartment",
        substance_mention="synthetic cholesterol", predicate="ACCUMULATES_IN_COMPARTMENT",
        quote="Synthetic cholesterol accumulated in the synthetic lysosome of synthetic disease alpha cells",
    )
    return stmt(**{**base, **kw})


def test_accumulation_claim_stores_the_substance_in_context(acc_resolver):
    rep = extract_claims(FakeClient([acc()]), ACC_SRC, acc_resolver)
    assert len(rep.claims) == 1 and not rep.quarantined
    assert rep.claims[0].context["substance"] == "CHEBI:900"
    assert (rep.claims[0].subject_id, rep.claims[0].object_id) == ("MONDO:0000001", "GO:0000900")


def test_accumulation_without_a_substance_is_quarantined(acc_resolver):
    rep = extract_claims(FakeClient([acc(substance_mention=None)]), ACC_SRC, acc_resolver)
    assert not rep.claims and "needs a substance" in rep.quarantined[0]["reason"]


def test_reversed_or_wrong_typed_statement_is_quarantined_with_the_expected_types(acc_resolver):
    # the first live run produced "cholesterol -> disease" (chemical as subject) for this predicate
    rep = extract_claims(
        FakeClient([acc(subject_mention="synthetic cholesterol", subject_type="chemical",
                        object_mention="synthetic disease alpha", object_type="disease")]),
        ACC_SRC, acc_resolver,
    )
    assert not rep.claims and "needs disease -> compartment, got chemical -> disease" in rep.quarantined[0]["reason"]


def test_unresolved_substance_is_quarantined(acc_resolver):
    rep = extract_claims(FakeClient([acc(substance_mention="not a real chemical")]), ACC_SRC, acc_resolver)
    assert not rep.claims and "chemical mention" in rep.quarantined[0]["reason"]


def test_pdf_ligature_in_source_still_matches_plain_text_quote(acc_resolver):
    rep = extract_claims(FakeClient([acc(quote="synthetic cholesterol accumulated in the synthetic lysosome of synthetic disease alpha cells, and findings were similar")]), ACC_SRC, acc_resolver)
    assert len(rep.claims) == 1


def test_prompt_lists_the_required_types_for_each_typed_predicate():
    for pred, (a, b) in PREDICATE_TYPES.items():
        assert f"- {pred}: {a} -> {b}" in SYSTEM_PROMPT


def test_prompt_asks_for_one_statement_per_compartment_in_singular_names():
    assert "ONE statement per compartment" in SYSTEM_PROMPT and "'late endosome', 'lysosome'" in SYSTEM_PROMPT


def test_prompt_makes_the_substance_required_for_accumulation_claims():
    assert "REQUIRED, never null" in SYSTEM_PROMPT and "ONE statement per" in SYSTEM_PROMPT
