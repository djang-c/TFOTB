"""Claims from structured reference files, without a language model.

A row of a pinned public file becomes a Claim whose `source_span` is the row itself, verbatim, and
whose `extraction_method` is "structured_field". Nothing is inferred: one row, one claim, the IDs
mapped through the resolver's cross-references (never built from labels). Claims are `unreviewed`.

So far: HPO genes_to_disease -> GENE_ASSOCIATED_WITH_DISEASE (gene -> disease). The dna_variants
channel reads these at gene level only, so a shared gene never makes a mechanism lead (docs 05).
"""

from __future__ import annotations

import hashlib
from typing import Any

from atlas.resolver import GENE, Resolver
from atlas.schemas import Claim, ClaimStatus, SourceType

G2D_URL = "https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/genes_to_disease.txt"
G2D_COLUMNS = ("ncbi_gene_id", "gene_symbol", "association_type", "disease_id", "source")


def _mondo_xref(disease_id: str) -> str:
    prefix, _, num = disease_id.partition(":")
    return f"Orphanet:{num}" if prefix == "ORPHA" else disease_id


def gene_disease_claims(
    rows: list[dict[str, str]], resolver: Resolver, *, exclude: set[str] = frozenset(), url: str = G2D_URL,
) -> tuple[list[Claim], dict[str, int]]:
    """HPO gene-disease rows -> claims. Returns the claims and a tally of what happened to each row,
    so coverage counts come from this step, not from generated text."""
    claims: list[Claim] = []
    tally = {"rows": 0, "claims": 0, "gene_unresolved": 0, "disease_unmapped": 0}
    for row in rows:
        tally["rows"] += 1
        gene = resolver.resolve(row["gene_symbol"], GENE).resolved_id
        if not gene:
            tally["gene_unresolved"] += 1
            continue
        diseases = sorted(resolver.ids_for_xref(_mondo_xref(row["disease_id"])) - set(exclude))
        if not diseases:
            tally["disease_unmapped"] += 1
            continue
        span = "\t".join(row.get(c, "") for c in G2D_COLUMNS)
        for mondo in diseases:
            digest = hashlib.sha256(f"{span}|{mondo}".encode()).hexdigest()[:16]
            claims.append(Claim(
                claim_id=f"CLAIM:hpo-g2d-{digest}",
                subject_id=gene,
                predicate="GENE_ASSOCIATED_WITH_DISEASE",
                object_id=mondo,
                source_url=url,
                source_span=span,
                source_type=SourceType.database_record,
                status=ClaimStatus.reported_observation,
                lineage_id=f"SOURCE:{row['disease_id']}",
                context={"association_type": row["association_type"].lower(), "via": row["disease_id"],
                         "upstream": row.get("source", "")},
                extraction_method="structured_field",
            ))
            tally["claims"] += 1
    return claims, tally


def as_api(claim: Claim) -> dict[str, Any]:
    return claim.model_dump(mode="json")
