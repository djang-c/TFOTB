"""T03 resolver tests. The small ontology below is SYNTHETIC (IDs and names are test-only)."""

from pathlib import Path

import pytest

from atlas.resolver import (
    DISEASE,
    GENE,
    TIER_EXACT,
    TIER_RELATED,
    Resolver,
    normalize,
    validate_variant_ref,
)

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture()
def r() -> Resolver:
    res = Resolver()
    res.add(DISEASE, "MONDO:0000001", "synthetic disease alpha", [("SDA", TIER_EXACT), ("shared name", TIER_EXACT)], ["Orphanet:1"])
    res.add(DISEASE, "MONDO:0000002", "synthetic disease beta", [("shared name", TIER_EXACT)], ["Orphanet:1"])
    res.add(DISEASE, "MONDO:0000003", "synthetic disease gamma type 1", [("looks similar", TIER_RELATED)])
    res.add(DISEASE, "MONDO:0000004", "synthetic disease gamma type 2", [])
    res.add(DISEASE, "MONDO:0000005", "umbrella", [("weak alias", TIER_RELATED)])
    res.add(DISEASE, "MONDO:0000006", "weak alias", [])
    res.add(DISEASE, "MONDO:0000007", "abbrev one", [("ABB", TIER_EXACT)])
    res.add(DISEASE, "MONDO:0000008", "abbrev two", [("ABB", TIER_RELATED)])
    res.add(GENE, "HGNC:100", "SYNA", [("OLDA", TIER_EXACT)])
    return res


def test_unique_label_resolves_with_method(r):
    out = r.resolve("Synthetic Disease Alpha", DISEASE)
    assert (out.status, out.resolved_id) == ("resolved", "MONDO:0000001")
    assert "label" in out.method


def test_unique_synonym_resolves(r):
    assert r.resolve("SDA", DISEASE).resolved_id == "MONDO:0000001"


def test_ambiguous_synonym_stays_unresolved_with_all_candidates(r):
    out = r.resolve("shared name", DISEASE)
    assert out.status == "ambiguous" and out.resolved_id is None
    assert {c.id for c in out.candidates} == {"MONDO:0000001", "MONDO:0000002"}


def test_label_beats_weaker_synonym_but_other_entry_is_disclosed(r):
    out = r.resolve("weak alias", DISEASE)
    assert out.resolved_id == "MONDO:0000006"
    assert "MONDO:0000005" in out.method


def test_abbreviation_used_by_stronger_and_weaker_entries_is_ambiguous(r):
    out = r.resolve("ABB", DISEASE)
    assert out.status == "ambiguous" and out.resolved_id is None
    assert {c.id for c in out.candidates} == {"MONDO:0000007", "MONDO:0000008"}


def test_label_built_ids_are_rejected(r):
    out = r.resolve("HGNC:SYNA", GENE)
    assert out.status == "unresolved" and out.resolved_id is None
    assert "malformed" in out.method


def test_wellformed_but_unknown_id_is_unresolved(r):
    assert r.resolve("HGNC:999", GENE).status == "unresolved"
    assert r.resolve("MONDO:0000001", GENE).status == "unresolved"  # wrong type


def test_wellformed_known_id_resolves(r):
    assert r.resolve("HGNC:100", GENE).resolved_id == "HGNC:100"


def test_type_filter_keeps_gene_and_disease_apart(r):
    assert r.resolve("SYNA", DISEASE).status == "unresolved"
    assert r.resolve("SYNA", GENE).resolved_id == "HGNC:100"


def test_close_but_different_names_are_suggestions_never_accepted(r):
    out = r.resolve("synthetic disease gamma type 3", DISEASE)
    assert out.status == "suggestions" and out.resolved_id is None
    assert {c.id for c in out.candidates} == {"MONDO:0000003", "MONDO:0000004"}


def test_no_match_is_unresolved(r):
    out = r.resolve("completely unrelated words", DISEASE)
    assert out.status == "unresolved" and out.candidates == []


def test_xref_ambiguity_not_merged(r):
    out = r.resolve_xref("orphanet:1")
    assert out.status == "ambiguous" and len(out.candidates) == 2


def test_add_rejects_wrong_namespace(r):
    with pytest.raises(ValueError):
        r.add(GENE, "MONDO:0000009", "x", [])


def test_normalize_ignores_case_punctuation_accents():
    assert normalize("Niemann–Pick  disease, TYPE C") == "niemann pick disease type c"
    assert normalize("Spielmeyer-Vogt") == normalize("spielmeyer vogt")


def test_variants_need_assembly_and_versioned_transcript():
    validate_variant_ref("GRCh38", "NM_000086.3")
    for assembly, transcript in [(None, "NM_000086.3"), ("hg19", "NM_000086.3"), ("GRCh38", "NM_000086"), ("GRCh38", None)]:
        with pytest.raises(ValueError):
            validate_variant_ref(assembly, transcript)


@pytest.fixture(scope="module")
def real() -> Resolver:
    return Resolver.from_raw(RAW)


@pytest.mark.skipif(not (RAW / "mondo" / "mondo.json").exists(), reason="pinned ontology files not downloaded")
class TestRealFiles:
    """Run only where scripts/fetch_ontologies.py has been run. Expected IDs were read from the files."""

    def test_seed_pair_and_genes(self, real):
        assert real.resolve("Niemann-Pick disease type C", DISEASE).resolved_id == "MONDO:0018982"
        assert real.resolve("juvenile neuronal ceroid lipofuscinosis", DISEASE).resolved_id == "MONDO:0019262"
        assert real.resolve("CLN3", GENE).resolved_id == "HGNC:2074"
        assert real.resolve("NPC1", GENE).resolved_id == "HGNC:7897"
        assert real.resolve("NPC2", GENE).resolved_id == "HGNC:14537"

    def test_paper_disease_name_is_ambiguous_between_two_cln3_entries(self, real):
        # PMID 37245481 studies "juvenile CLN3 disease"; MONDO uses that string for two entries.
        # A human must pick; the resolver must not.
        out = real.resolve("Juvenile CLN3 Disease", DISEASE)
        assert out.status == "ambiguous" and out.resolved_id is None
        assert {"MONDO:0008767", "MONDO:0979346"} <= {c.id for c in out.candidates}

    def test_npc_abbreviation_is_ambiguous_not_a_guess(self, real):
        out = real.resolve("NPC", DISEASE)
        assert out.status == "ambiguous" and out.resolved_id is None
        assert {"MONDO:0018982", "MONDO:0011775"} <= {c.id for c in out.candidates}

    def test_bare_cln3_is_ambiguous_across_species_entries(self, real):
        assert real.resolve("CLN3", DISEASE).status == "ambiguous"

    def test_gene_symbol_is_not_a_disease(self, real):
        assert real.resolve("NPC1", DISEASE).resolved_id != "HGNC:7897"
