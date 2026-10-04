from atlas.ranking import categorize, independent_support_count, shared_treatment_inference_allowed
from atlas.schemas import ChannelComparison, EvidenceCategory


def comp(ch, avail="available", **kw):
    return ChannelComparison(
        channel_id=ch, channel_version="t", query_id="q", candidate_id="c", availability=avail, **kw
    )


def test_missing_rna_is_missing_not_mismatch_or_confirmation(mk):
    c = comp("rna_effects", "missing")
    assert c.score is None and not c.context_mismatches and not c.supporting_claim_ids
    assert (
        categorize([c, comp("phenotype", score=0.4, score_definition="IC-sim v0")], {})
        == EvidenceCategory.symptom_level_lead
    )


def test_phenotype_only_never_reaches_mechanistic(mk):
    cat = categorize([comp("phenotype", score=0.99, score_definition="IC-sim v0")], {})
    assert cat is EvidenceCategory.symptom_level_lead


def test_reviewed_mechanism_gets_top_category(mk):
    c1 = mk(review_state="reviewed")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id])]
    assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.reviewed_mechanistic_lead


def test_unreviewed_mechanism_is_hypothesis_only(mk):
    c1 = mk()
    comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id])]
    assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.hypothesis_only


def test_contradiction_surfaces_and_blocks_shared_treatment(mk):
    c1, c2 = mk("CLAIM:a", review_state="reviewed"), mk("CLAIM:b", lineage="STUDY:s2")
    comps = [
        comp(
            "molecular_mechanisms",
            supporting_claim_ids=["CLAIM:a"],
            contradicting_claim_ids=["CLAIM:b"],
            context_mismatches=["effect_direction"],
        )
    ]
    assert (
        categorize(comps, {"CLAIM:a": c1, "CLAIM:b": c2}) is EvidenceCategory.conflicting_evidence
    )
    assert not shared_treatment_inference_allowed(comps)


def test_no_available_channel_is_insufficient_coverage():
    assert (
        categorize([comp("rna_effects", "missing"), comp("phenotype", "failed")], {})
        is EvidenceCategory.insufficient_coverage
    )


def test_duplicate_evidence_is_not_independent_replication(mk):
    a, b, c = (
        mk("CLAIM:1", lineage="STUDY:same"),
        mk("CLAIM:2", lineage="STUDY:same"),
        mk("CLAIM:3", lineage="STUDY:other"),
    )
    claims = {x.claim_id: x for x in (a, b, c)}
    assert independent_support_count(["CLAIM:1", "CLAIM:2"], claims) == 1
    assert independent_support_count(["CLAIM:1", "CLAIM:2", "CLAIM:3"], claims) == 2


def test_tissue_mismatch_caveat_is_retained():
    c = comp("rna_effects", context_mismatches=["tissue"], limitations=["different tissue"])
    assert "tissue" in c.context_mismatches and shared_treatment_inference_allowed([c])


def test_simulation_success_never_counts_as_biological_support(mk):
    sim = mk("CLAIM:sim", pred="SIMULATES_WORKFLOW_FOR", review_state="reviewed")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=["CLAIM:sim"])]
    assert categorize(comps, {"CLAIM:sim": sim}) is EvidenceCategory.hypothesis_only


def test_hypothesis_only_claim_never_makes_a_reviewed_mechanistic_lead(mk):
    c1 = mk(pred="SHARES_PATHOGENIC_PATHWAY_WITH", status="inference", review_state="reviewed")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id])]
    assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.hypothesis_only


def test_gene_data_without_a_shared_gene_does_not_demote_a_symptom_lead():
    # Found on real HPO data: CLN1 vs CLN3 (different genes) fell to "hypothesis only" while
    # candidates with no gene data at all stayed "symptom-level lead".
    no_shared_gene = comp("dna_variants", limitations=["both diseases have claims here but share no feature"])
    pheno = comp("phenotype", score=0.66, score_definition="BMA-Lin")
    assert categorize([pheno, no_shared_gene], {}) is EvidenceCategory.symptom_level_lead
    assert categorize([no_shared_gene], {}) is EvidenceCategory.hypothesis_only


def test_unreviewed_observation_from_a_published_source_is_literature_supported_not_hypothesis(mk):
    c1 = mk(source_type="published")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id])]
    assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.literature_supported_lead


def test_uploads_fixtures_and_hypotheses_never_become_literature_supported(mk):
    for kw in ({"source_type": "lab_reported"}, {"source_type": "synthetic_fixture"},
               {"source_type": "published", "status": "inference", "pred": "ASSOCIATED_WITH_PHENOTYPE"},
               {"source_type": "published", "status": "computational_prediction"},
               {"source_type": "published", "pred": "SHARES_PATHOGENIC_PATHWAY_WITH", "status": "inference"}):
        c1 = mk(**kw)
        comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id])]
        assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.hypothesis_only, kw


def test_one_non_published_claim_among_the_support_keeps_the_connection_hypothesis_only(mk):
    a, b = mk("CLAIM:a", source_type="published"), mk("CLAIM:b", source_type="lab_reported")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=["CLAIM:a", "CLAIM:b"])]
    assert categorize(comps, {"CLAIM:a": a, "CLAIM:b": b}) is EvidenceCategory.hypothesis_only


def test_a_contradiction_still_beats_literature_support(mk):
    c1 = mk(source_type="published")
    comps = [comp("molecular_mechanisms", supporting_claim_ids=[c1.claim_id], contradicting_claim_ids=["CLAIM:x"])]
    assert categorize(comps, {c1.claim_id: c1}) is EvidenceCategory.conflicting_evidence
