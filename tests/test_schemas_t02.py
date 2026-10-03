"""T02 contracts: Entity, CoverageManifest, GapResult, AssetResult, ActionCard.
All data is SYNTHETIC (format-valid placeholders, no biological claim)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas.schemas import (
    ActionCard,
    AssetResult,
    Claim,
    CoverageManifest,
    Entity,
    GapResult,
    validate_curie,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
SYN = "https://example.invalid/synthetic"


def entity(**kw):
    base = dict(
        id="MONDO:0000001", type="disease", label="SYNTHETIC disease", source_url=SYN,
        source_type="synthetic_fixture", retrieved_at="2026-10-03",
    )
    return Entity(**{**base, **kw})


def manifest(**kw):
    base = dict(
        manifest_id="COV:syn-1", query="SYNTHETIC", dataset_version="synthetic-0",
        retrieved_at="2026-10-03T00:00:00Z", generated_by="test@0",
        per_source=[{"source": "syn", "status": "ok", "fetched": 2, "screened": 1}],
    )
    return CoverageManifest(**{**base, **kw})


def gap(**kw):
    base = dict(
        kind="no_supported_route", as_of="2026-10-03", coverage_manifest_id="COV:syn-1",
        statement="No supported route found in the indexed evidence as of 2026-10-03.",
        missing_information=["SYNTHETIC"], reviewer_role="domain expert",
    )
    return GapResult(**{**base, **kw})


def asset(**kw):
    base = dict(
        asset_id="ASSET:syn-1", asset_kind="registry", label="SYNTHETIC registry",
        source_url=SYN, relevance_claim_ids=["CLAIM:syn-1"],
    )
    return AssetResult(**{**base, **kw})


def card(**kw):
    base = dict(
        card_id="CARD:syn-1", kind="evidence_brief", audience="science",
        this_week="SYNTHETIC: review the cited claim.", responsible_human="domain expert",
        body_markdown="SYNTHETIC [^c:CLAIM:syn-1]", claim_ids=["CLAIM:syn-1"],
        limitations=["synthetic"], generated_by="template",
    )
    return ActionCard(**{**base, **kw})


CONTACT = {"label": "org page", "url": "https://example.invalid/contact", "source_url": SYN,
           "verified_at": "2026-10-03"}


@pytest.mark.parametrize("good", ["NCBIGene:2629", "ORPHA:355", "PMID:123", "ORG:syn-lab",
                                  "ORCID:0000-0002-1825-0097", "infores:clinvar",
                                  "ENSEMBL:ENSG00000177628", "UNRESOLVED:q1"])
def test_new_prefixes_accepted(good):
    assert validate_curie(good) == good


@pytest.mark.parametrize("bad", ["NCBIGene:GBA1", "CASE-SYN-1", "ORCID:123", "ENSEMBL:GBA1",
                                 "UniProtKB:SLC2A1"])
def test_label_built_or_private_ids_rejected(bad):
    with pytest.raises(ValueError):
        validate_curie(bad)


def test_valid_models_build():
    entity(), manifest(), gap(), asset(), card()


@pytest.mark.parametrize("kw", [
    dict(id="HP:0000001"),  # wrong namespace for a disease
    dict(id="UNRESOLVED:q1"),  # resolved status with placeholder id
    dict(candidate_ids=["MONDO:0000002"]),  # resolved entity with candidates
    dict(id="CASE-SYN-1"),
    dict(type="variant", id="VARIANT:syn-1", attributes={"assembly": "GRCh38",
                                                         "hgvs": "NM_000157:c.1A>G"}),
    dict(type="asset", id="ASSET:syn-1", attributes={"asset_kind": "rumour"}),
    dict(type="organization", id="ORG:syn", attributes={"contact": "someone@example.org"}),
    dict(extra_field=1),
    dict(type="gene", id="ENSEMBL:ENSP00000000001"),  # protein ID typed as gene
    dict(type="transcript", id="ENSEMBL:ENSG00000000001"),
    dict(type="investigator", id="INV:syn", attributes={"contacts": ["jane@example.org"]}),
    dict(attributes={"lab": {"email": "x@example.org"}}),  # nested, any entity type
    dict(xrefs=["HGNC:GBA1"]),
    dict(schema_version="0.1"),
])
def test_invalid_entities(kw):
    with pytest.raises(ValidationError):
        entity(**kw)


def test_unresolved_and_ambiguous_entities_stay_unresolved():
    e = entity(id="UNRESOLVED:q1", identity_status="ambiguous",
               candidate_ids=["MONDO:0000001", "MONDO:0000002"])
    assert e.id == "UNRESOLVED:q1"
    with pytest.raises(ValidationError):
        entity(id="MONDO:0000001", identity_status="unresolved")
    with pytest.raises(ValidationError):
        entity(id="UNRESOLVED:q1", identity_status="ambiguous", candidate_ids=["MONDO:0000001"])


def test_variant_needs_versioned_transcript():
    v = entity(type="variant", id="VARIANT:syn-1",
               attributes={"assembly": "GRCh38", "hgvs": "NM_000157.4:c.1A>G"})
    assert v.attributes["hgvs"].startswith("NM_000157.4")


@pytest.mark.parametrize("src", [
    {"source": "s", "status": "ok", "fetched": 2},  # ok without screened count
    {"source": "s", "status": "not_queried", "fetched": 0, "screened": 0},  # missing as zero
    {"source": "s", "status": "failed"},  # failed without error
    {"source": "s", "status": "ok", "fetched": 1, "screened": 2},
    {"source": "s", "status": "ok", "fetched": -1, "screened": 0},
])
def test_invalid_coverage(src):
    with pytest.raises(ValidationError):
        manifest(per_source=[src])


def test_coverage_missing_is_none_not_zero():
    m = manifest(per_source=[{"source": "s", "status": "unavailable"}],
                 per_channel=[{"channel_id": "rna_effects", "availability": "missing"}])
    assert m.per_source[0].fetched is None


@pytest.mark.parametrize("kw", [
    dict(statement="No treatment exists for this disease as of 2026-10-03."),
    dict(statement="A registry does not exist (2026-10-03)."),
    dict(statement="No supported route found in the indexed evidence."),  # no date
    dict(statement="No therapies exist as of 2026-10-03."),
    dict(statement="No registries are available as of 2026-10-03."),
    dict(entity_id="HGNC:GBA1"),
    dict(known_claim_ids=["whatever"]),
    dict(missing_information=[]),
    dict(reviewer_role=""),
    dict(kind="supported_research_route"),
    dict(coverage_manifest_id="CLAIM:syn-1"),
])
def test_invalid_gaps(kw):
    with pytest.raises(ValidationError):
        gap(**kw)


@pytest.mark.parametrize("kw", [
    dict(relevance_claim_ids=[]),
    dict(status="active"),  # status without source/date
    dict(contact={**CONTACT, "url": "mailto:a@example.org"}),
    dict(contact={**CONTACT, "url": "https://example.invalid/a@example.org"}),
    dict(category="reviewed mechanistic lead"),  # assets carry no biology category
    dict(score=0.5),
])
def test_invalid_assets(kw):
    with pytest.raises(ValidationError):
        asset(**kw)


def test_asset_status_with_source_ok():
    a = asset(status="active", status_source_url=SYN, status_checked_at="2026-10-03",
              contact=CONTACT)
    assert a.contact.url.startswith("https://")


@pytest.mark.parametrize("kw", [
    dict(body_markdown="SYNTHETIC [^c:CLAIM:other]"),  # dangling footnote
    dict(responsible_human="   "),
    dict(this_week="Patient should take 10 mg daily."),
    dict(body_markdown="The family is eligible for the trial [^c:CLAIM:syn-1]"),
    dict(generated_by="gpt"),
    dict(kind="asset_reuse"),  # no asset_ids
    dict(limitations=[]),
    dict(card_id="CLAIM:syn-1"),
    dict(body_markdown="See [^CLAIM:syn-1]"),  # non-canonical footnote form
    dict(body_markdown="give 10mg/kg daily [^c:CLAIM:syn-1]"),
    dict(body_markdown="increase the doses [^c:CLAIM:syn-1]"),
    dict(body_markdown="they are ineligible for it [^c:CLAIM:syn-1]"),
    dict(limitations=["should take with food"]),
    dict(claim_ids=["CLAIM:syn-1", "not-an-id"]),
    dict(entity_id="HGNC:GBA1"),
])
def test_invalid_cards(kw):
    with pytest.raises(ValidationError):
        card(**kw)


def test_resolved_ensembl_and_uniprot_ok():
    entity(type="gene", id="ENSEMBL:ENSG00000177628")
    entity(type="transcript", id="ENSEMBL:ENST00000368373")
    entity(type="protein", id="UniProtKB:P04062")


def test_stale_or_label_built_claim_refs_rejected(mk):
    with pytest.raises(ValidationError):
        mk(schema_version="0.1")
    with pytest.raises(ValidationError):
        mk(derived_from=["some label"])


def test_contract_fixtures_validate():
    """Frontend mock fixtures must match the models (catches fixture/model drift)."""
    def load(name):
        d = json.loads((FIXTURES / f"{name}.json").read_text())
        d.pop("_synthetic")
        return d

    Entity(**load("entity")["entity"])
    Entity(**load("search")["resolved"])
    CoverageManifest(**load("connections")["coverage"])
    Claim(**load("claim")["claim"])
    GapResult(**load("gap"))
    ActionCard(**load("action"))
    for a in load("assets")["assets"]:
        AssetResult(**a)
