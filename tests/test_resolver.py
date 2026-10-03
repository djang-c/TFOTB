"""T03 resolver tests. The small ontology below is SYNTHETIC (IDs and names are test-only)."""

import json
from pathlib import Path

import pytest

from atlas.resolver import (
    CHEMICAL,
    COMPARTMENT,
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

    def test_paper_disease_name_is_ambiguous_between_two_cln3_entries(self, real, monkeypatch):
        # PMID 37245481 studies "juvenile CLN3 disease"; MONDO uses that string for two entries.
        # Without the owner alias a human must pick; the resolver must not.
        monkeypatch.setattr(real, "_aliases", {})
        out = real.resolve("Juvenile CLN3 Disease", DISEASE)
        assert out.status == "ambiguous" and out.resolved_id is None
        assert {"MONDO:0008767", "MONDO:0979346"} <= {c.id for c in out.candidates}

    def test_owner_aliases_settle_the_two_seed_names_and_say_so(self, real):
        out = real.resolve("juvenile CLN3 disease", DISEASE)
        assert out.resolved_id == "MONDO:0008767" and "owner-approved alias" in out.method
        assert real.resolve("NPC", DISEASE).resolved_id == "MONDO:0018982"

    def test_npc_abbreviation_is_ambiguous_not_a_guess(self, real, monkeypatch):
        monkeypatch.setattr(real, "_aliases", {})
        out = real.resolve("NPC", DISEASE)
        assert out.status == "ambiguous" and out.resolved_id is None
        assert {"MONDO:0018982", "MONDO:0011775"} <= {c.id for c in out.candidates}

    def test_bare_cln3_is_ambiguous_across_species_entries(self, real):
        assert real.resolve("CLN3", DISEASE).status == "ambiguous"

    def test_gene_symbol_is_not_a_disease(self, real):
        assert real.resolve("NPC1", DISEASE).resolved_id != "HGNC:7897"


def test_outer_name_wins_over_the_bracketed_abbreviation(r):
    out = r.resolve("synthetic disease alpha (synthetic disease beta)", DISEASE)
    assert (out.status, out.resolved_id) == ("resolved", "MONDO:0000001") and "bracketed" in out.method


def test_bracket_is_used_only_when_the_outer_name_does_not_resolve(r):
    out = r.resolve("some unknown words (synthetic disease alpha) here", DISEASE)
    assert (out.status, out.resolved_id) == ("resolved", "MONDO:0000001") and "bracketed 'synthetic" in out.method


def test_bracketed_parts_naming_different_entities_stay_ambiguous(r):
    out = r.resolve("unknown words (synthetic disease alpha) (synthetic disease beta)", DISEASE)
    assert out.status == "ambiguous" and out.resolved_id is None
    assert {c.id for c in out.candidates} == {"MONDO:0000001", "MONDO:0000002"}


def test_bracketed_mention_with_no_matching_part_is_unresolved(r):
    assert r.resolve("nothing like it (zzz)", DISEASE).status == "unresolved"


def test_chemical_and_compartment_types_are_separate_namespaces(r):
    r.add(CHEMICAL, "CHEBI:16113", "cholesterol", [])
    r.add(COMPARTMENT, "GO:0005764", "lysosome", [("lytic vacuole", TIER_EXACT)])
    assert r.resolve("Cholesterol", CHEMICAL).resolved_id == "CHEBI:16113"
    assert r.resolve("lysosome", COMPARTMENT).resolved_id == "GO:0005764"
    assert r.resolve("cholesterol", DISEASE).status == "unresolved"  # wrong type never resolves
    with pytest.raises(ValueError):
        r.add(CHEMICAL, "GO:0005764", "wrong prefix", [])


def test_alias_applies_only_when_plain_match_does_not_resolve(r, tmp_path):
    f = tmp_path / "aliases.json"
    f.write_text(json.dumps({"aliases": [
        {"type": "disease", "mention": "shared name", "id": "MONDO:0000002", "note": "test"},
        {"type": "disease", "mention": "synthetic disease alpha", "id": "MONDO:0000002", "note": "test: must NOT override"},
    ]}))
    assert r.load_aliases(f) == 2
    assert r.resolve("shared name", DISEASE).resolved_id == "MONDO:0000002"  # ambiguous plain -> alias
    assert "alias" in r.resolve("shared name", DISEASE).method
    assert r.resolve("synthetic disease alpha", DISEASE).resolved_id == "MONDO:0000001"  # unique label wins


def test_alias_to_an_id_missing_from_the_ontology_is_rejected(r, tmp_path):
    f = tmp_path / "aliases.json"
    f.write_text(json.dumps({"aliases": [{"type": "disease", "mention": "x", "id": "MONDO:9999999", "note": "t"}]}))
    with pytest.raises(ValueError):
        r.load_aliases(f)


@pytest.mark.skipif(not (RAW / "go" / "go-basic.json").exists(), reason="GO/ChEBI not downloaded")
def test_real_go_and_chebi_resolve_the_seed_paper_terms():
    real = Resolver.from_raw(RAW)
    assert real.resolve("lysosome", COMPARTMENT).resolved_id == "GO:0005764"
    assert real.resolve("cholesterol", CHEMICAL).resolved_id == "CHEBI:16113"
    assert real.resolve("lysosome", CHEMICAL).status != "resolved"
    assert real.resolve("Niemann-Pick Type C (NPC) disease", DISEASE).resolved_id == "MONDO:0018982"
    assert real.resolve("juvenile CLN3 disease (JNCL)", DISEASE).resolved_id == "MONDO:0008767"
