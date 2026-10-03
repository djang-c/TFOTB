"""Structured-file claims. Rows and IDs below are SYNTHETIC (format-valid placeholders)."""

from atlas.resolver import DISEASE, GENE, Resolver
from atlas.structured import gene_disease_claims


def resolver() -> Resolver:
    r = Resolver()
    r.add(DISEASE, "MONDO:9000001", "Example disease", [], ["OMIM:900001", "Orphanet:900002"])
    r.add(GENE, "HGNC:900001", "EXG1", [])
    return r


ROW = {"ncbi_gene_id": "NCBIGene:1", "gene_symbol": "EXG1", "association_type": "MENDELIAN",
       "disease_id": "OMIM:900001", "source": "synthetic"}


def test_row_becomes_a_quoted_unreviewed_database_claim():
    claims, tally = gene_disease_claims([ROW], resolver())
    (c,) = claims
    assert (c.subject_id, c.predicate, c.object_id) == ("HGNC:900001", "GENE_ASSOCIATED_WITH_DISEASE", "MONDO:9000001")
    assert c.source_span == "NCBIGene:1\tEXG1\tMENDELIAN\tOMIM:900001\tsynthetic"
    assert c.source_type.value == "database_record" and c.review_state.value == "unreviewed"
    assert c.extraction_method == "structured_field"
    assert tally == {"rows": 1, "claims": 1, "gene_unresolved": 0, "disease_unmapped": 0}


def test_orphanet_ids_map_through_mondo_xrefs():
    claims, _ = gene_disease_claims([{**ROW, "disease_id": "ORPHA:900002"}], resolver())
    assert claims[0].object_id == "MONDO:9000001"


def test_unresolved_rows_are_counted_not_guessed():
    rows = [{**ROW, "gene_symbol": "NOPE1"}, {**ROW, "disease_id": "OMIM:999999"}]
    claims, tally = gene_disease_claims(rows, resolver())
    assert claims == [] and tally["gene_unresolved"] == 1 and tally["disease_unmapped"] == 1


def test_claim_ids_are_deterministic():
    a, _ = gene_disease_claims([ROW], resolver())
    b, _ = gene_disease_claims([ROW], resolver())
    assert a[0].claim_id == b[0].claim_id
