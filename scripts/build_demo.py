"""Build the SYNTHETIC demo dataset served by the stub API (data/fixtures/demo.json).

Every record is constructed through the T02 Pydantic models, so the demo obeys the same rules as
real data. All entities use the SYN: namespace and placeholder labels: this file makes NO
biological claim. Real data replaces it after T01/T04. Deterministic: same code -> same bytes.

    python scripts/build_demo.py
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from atlas.schemas import (
    ActionCard,
    AssetResult,
    ChannelComparison,
    Claim,
    ConnectionResult,
    CoverageManifest,
    Entity,
    EvidenceCategory,
    GapResult,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fixtures" / "demo.json"
SIM_DIR = ROOT / "data" / "fixtures" / "sim"
AS_OF = "2026-10-03"
SYN_URL = "https://example.invalid/synthetic"
LABEL = (
    "SYNTHETIC demo dataset for UI/contract development. Placeholder entities and quotes; "
    "makes NO biological claim."
)


def ent(slug, type_, label, synonyms=(), **attrs):
    return Entity(
        id=f"SYN:{slug}", type=type_, label=label, synonyms=synonyms, attributes=attrs,
        source_url=SYN_URL, source_type="synthetic_fixture", source_version="synthetic-0",
        retrieved_at=AS_OF,
    )


ENTITIES = [
    ent("disease-a", "disease", "Disease A (synthetic)", ("Syndrome A", "DA type 1"),
        summary_known="Linked to reduced activity of mechanism M1 in two synthetic reports.",
        summary_missing="No RNA-level findings are indexed."),
    ent("disease-b", "disease", "Disease B (synthetic)", ("Syndrome B",)),
    ent("disease-c", "disease", "Disease C (synthetic)"),
    ent("disease-d", "disease", "Disease D (synthetic)"),
    ent("disease-e", "disease", "Disease E (synthetic)"),
    ent("gene-1", "gene", "Gene G1 (synthetic)"),
    ent("gene-2", "gene", "Gene G2 (synthetic)"),
    ent("gene-3", "gene", "Gene G3 (synthetic)"),
    ent("variant-vus-1", "variant", "Uncertain variant in G1 (synthetic)",
        assembly="SYNTHETIC", hgvs="NM_000000.1:c.0A>G", is_synthetic=True,
        source_reported_classification="uncertain significance (synthetic)"),
    ent("mech-1", "mechanism", "Mechanism M1 (synthetic)"),
    ent("mech-2", "mechanism", "Mechanism M2 (synthetic)"),
    *[ent(f"pheno-{i}", "phenotype", f"Phenotype P{i} (synthetic)") for i in range(1, 7)],
    ent("registry-b", "asset", "Natural-history registry for Disease B (synthetic)",
        asset_kind="registry"),
    ent("cellmodel-b", "asset", "Cell model for Disease B (synthetic)", asset_kind="cell_model"),
    ent("org-b", "organization", "Disease B patient group (synthetic)",
        website="https://example.invalid/org-b"),
    ent("study-1", "study", "Study S1 (synthetic)"),
    ent("study-2", "study", "Study S2 (synthetic)"),
    ent("study-3", "study", "Study S3 (synthetic)"),
]
BY_ID = {e.id: e for e in ENTITIES}

_n = 0


def claim(subj, pred, obj, span, lineage, status="reported_observation", review="unreviewed",
          source_type="synthetic_fixture", **kw):
    global _n
    _n += 1
    return Claim(
        claim_id=f"CLAIM:syn-{_n}", subject_id=f"SYN:{subj}", predicate=pred,
        object_id=f"SYN:{obj}", source_url=SYN_URL, source_span=span, source_type=source_type,
        status=status, review_state=review, lineage_id=f"STUDY:{lineage}",
        retrieved_at=AS_OF, published_at="2025-01-15",
        extraction_method="structured_field (synthetic)", **kw,
    )


Q = '"{}" (synthetic quote)'.format
CLAIMS = [
    # Disease A phenotypes (1-4) and Disease B / C overlap
    *[claim("disease-a", "ASSOCIATED_WITH_PHENOTYPE", f"pheno-{i}",
            Q(f"Patients with Disease A presented with Phenotype P{i}."), "syn-s1",
            review="reviewed", knowledge_level="observation", agent_type="manual_agent")
      for i in range(1, 5)],
    *[claim("disease-b", "ASSOCIATED_WITH_PHENOTYPE", f"pheno-{i}",
            Q(f"Phenotype P{i} was reported in the Disease B cohort."), "syn-s2")
      for i in (1, 2, 5)],
    *[claim("disease-c", "ASSOCIATED_WITH_PHENOTYPE", f"pheno-{i}",
            Q(f"Disease C cases showed Phenotype P{i}."), "syn-s3")
      for i in (1, 2, 3, 4)],
    # Mechanism: A and B both decrease M1 (concordant); two descriptions of one experiment
    claim("disease-a", "PERTURBS_MECHANISM", "mech-1",
          Q("Loss of G1 function reduced M1 activity in patient-derived cells."), "syn-s1",
          review="reviewed", context={"direction": "decreases", "tissue": "fibroblast (synthetic)",
                                      "organism": "human"},
          knowledge_level="observation", agent_type="manual_agent"),
    claim("disease-a", "PERTURBS_MECHANISM", "mech-1",
          Q("Reduced M1 activity, as described in the S1 cell experiment."), "syn-s1",
          context={"direction": "decreases", "tissue": "fibroblast (synthetic)"},
          derived_from=("CLAIM:syn-12",)),
    claim("disease-b", "PERTURBS_MECHANISM", "mech-1",
          Q("Disease B cells showed decreased M1 activity."), "syn-s2", review="reviewed",
          context={"direction": "decreases", "tissue": "fibroblast (synthetic)",
                   "organism": "human"}),
    claim("gene-1", "PERTURBS_MECHANISM", "mech-1", Q("G1 knockdown lowered M1 activity."),
          "syn-s1", context={"direction": "decreases"}),
    claim("gene-2", "PERTURBS_MECHANISM", "mech-1", Q("G2 variants lowered M1 activity."),
          "syn-s2", context={"direction": "decreases"}),
    # Opposite direction: A decreases M2, D increases M2
    claim("disease-a", "PERTURBS_MECHANISM", "mech-2", Q("M2 output was reduced in Disease A."),
          "syn-s1", context={"direction": "decreases"}),
    claim("disease-d", "PERTURBS_MECHANISM", "mech-2",
          Q("Disease D samples showed increased M2 output."), "syn-s3",
          context={"direction": "increases"}),
    claim("gene-3", "PERTURBS_MECHANISM", "mech-2", Q("G3 gain of function raised M2 output."),
          "syn-s3", context={"direction": "increases"}),
    # Hypothesis only: E linked to M1 by inference (weak predicate, so allowed)
    claim("disease-e", "ASSOCIATED_WITH_PHENOTYPE", "pheno-6",
          Q("Phenotype P6 noted in one Disease E case."), "syn-s3"),
    claim("disease-e", "SUPPORTED_BY", "mech-1",
          Q("Authors speculate M1 may be involved in Disease E."), "syn-s3", status="inference"),
    # Prediction + contradiction pair on the RNA level for B
    claim("gene-2", "HAS_PREDICTED_RNA_EFFECT", "mech-1",
          Q("Splice predictor flags a possible exon skip."), "syn-s2",
          status="computational_prediction", score=0.71,
          score_definition="synthetic splice-predictor delta score, v0 (not a probability)"),
    # Lab-reported upload (unreviewed)
    claim("disease-b", "PERTURBS_MECHANISM", "mech-1",
          Q("Our lab saw no change in M1 in a small Disease B sample."), "syn-lab1",
          source_type="lab_reported", contributor="Synthetic Lab (demo)",
          context={"direction": "no_change"}, review_notes=("awaiting reviewer",),
          contradicts=("CLAIM:syn-14",)),
    # Assets
    claim("registry-b", "ASSET_RELEVANT_TO", "disease-b",
          Q("The registry enrols people with Disease B and records phenotypes P1, P2, P5."),
          "syn-reg"),
    claim("cellmodel-b", "ASSET_RELEVANT_TO", "disease-b",
          Q("Cell line derived from a Disease B donor; M1 assay validated."), "syn-cell"),
    claim("disease-b", "INVESTIGATED_IN", "study-2", Q("Disease B natural-history study S2."),
          "syn-s2"),
]
CLAIM_BY_ID = {c.claim_id: c for c in CLAIMS}


def cids(subj=None, obj=None, pred=None, lineage=None):
    return [
        c.claim_id for c in CLAIMS
        if (subj is None or c.subject_id == f"SYN:{subj}")
        and (obj is None or c.object_id == f"SYN:{obj}")
        and (pred is None or c.predicate == pred)
        and (lineage is None or c.lineage_id == f"STUDY:{lineage}")
    ]


def comp(channel, cand, availability, score=None, definition=None, sup=(), con=(), **kw):
    return ChannelComparison(
        channel_id=channel, channel_version="synthetic-0", query_id="SYN:disease-a",
        candidate_id=f"SYN:{cand}", availability=availability, score=score,
        score_definition=definition, supporting_claim_ids=list(sup),
        contradicting_claim_ids=list(con), **kw,
    )


JACCARD = "phenotype Jaccard overlap over indexed phenotypes (0-1), synthetic-0"
PHENO_A = cids("disease-a", pred="ASSOCIATED_WITH_PHENOTYPE")

CONNECTIONS = {
    "SYN:disease-a": [
        ConnectionResult(
            query_id="SYN:disease-a", candidate_id="SYN:disease-b",
            category=EvidenceCategory.reviewed_mechanistic_lead, coverage_manifest_id="COV:syn-a",
            path_claim_ids=["CLAIM:syn-12", "CLAIM:syn-14"],
            shared_treatment_inference_allowed=False,
            compatibility_flags=["same tissue (fibroblast, synthetic)", "same direction (decreases)"],
            comparisons=[
                comp("phenotype", "disease-b", "available", 0.4, JACCARD,
                     sup=PHENO_A[:2] + cids("disease-b", pred="ASSOCIATED_WITH_PHENOTYPE")[:2]),
                comp("dna", "disease-b", "available", None, None,
                     sup=["CLAIM:syn-15", "CLAIM:syn-16"],
                     limitations=["gene-level only; no shared variant"]),
                comp("rna", "disease-b", "missing", missing_fields=["RNA findings for Disease A"],
                     limitations=["only a computational prediction exists for Disease B"]),
                comp("mechanism", "disease-b", "available", None, None,
                     sup=["CLAIM:syn-12", "CLAIM:syn-14"], con=["CLAIM:syn-23"],
                     context_matches=["tissue", "direction"]),
            ],
        ),
        ConnectionResult(
            query_id="SYN:disease-a", candidate_id="SYN:disease-c",
            category=EvidenceCategory.symptom_level_lead, coverage_manifest_id="COV:syn-a",
            path_claim_ids=PHENO_A[:2],
            compatibility_flags=["symptoms overlap; biology not shown to match"],
            comparisons=[
                comp("phenotype", "disease-c", "available", 1.0, JACCARD,
                     sup=PHENO_A + cids("disease-c")),
                comp("dna", "disease-c", "missing", missing_fields=["gene findings for Disease C"]),
                comp("rna", "disease-c", "missing", missing_fields=["RNA findings"]),
                comp("mechanism", "disease-c", "missing",
                     missing_fields=["mechanism findings for Disease C"]),
            ],
        ),
        ConnectionResult(
            query_id="SYN:disease-a", candidate_id="SYN:disease-d",
            category=EvidenceCategory.conflicting_evidence, coverage_manifest_id="COV:syn-a",
            path_claim_ids=["CLAIM:syn-17", "CLAIM:syn-18"],
            compatibility_flags=[(
                "Opposite effect direction - shared treatment not supported; "
                "research connection still shown"
            )],
            comparisons=[
                comp("phenotype", "disease-d", "available", 0.0, JACCARD,
                     limitations=["no indexed phenotype overlap"]),
                comp("dna", "disease-d", "failed", limitations=["gene source timed out (synthetic)"]),
                comp("rna", "disease-d", "missing", missing_fields=["RNA findings"]),
                comp("mechanism", "disease-d", "available", sup=["CLAIM:syn-17", "CLAIM:syn-18"],
                     context_mismatches=["direction: decreases vs increases"]),
            ],
        ),
        ConnectionResult(
            query_id="SYN:disease-a", candidate_id="SYN:disease-e",
            category=EvidenceCategory.hypothesis_only, coverage_manifest_id="COV:syn-a",
            path_claim_ids=["CLAIM:syn-21"],
            comparisons=[
                comp("phenotype", "disease-e", "available", 0.0, JACCARD),
                comp("dna", "disease-e", "missing", missing_fields=["gene findings"]),
                comp("rna", "disease-e", "missing", missing_fields=["RNA findings"]),
                comp("mechanism", "disease-e", "incompatible", sup=["CLAIM:syn-21"],
                     limitations=["only an author inference; no observation"]),
            ],
        ),
    ]
}

MANIFESTS = [
    CoverageManifest(
        manifest_id="COV:syn-a", query="Disease A (synthetic)", dataset_version="synthetic-0",
        source_versions={"synthetic": "0"}, retrieved_at=f"{AS_OF}T00:00:00Z",
        generated_by="scripts/build_demo.py@0",
        per_source=[
            {"source": "synthetic literature", "version": "0", "status": "ok",
             "fetched": 14, "screened": 9},
            {"source": "synthetic variant db", "version": "0", "status": "ok",
             "fetched": 3, "screened": 3},
            {"source": "synthetic gene db", "status": "failed", "error": "timeout (synthetic)"},
            {"source": "synthetic RNA atlas", "status": "not_queried"},
        ],
        per_channel=[
            {"channel_id": "phenotype", "availability": "available"},
            {"channel_id": "dna", "availability": "available"},
            {"channel_id": "rna", "availability": "missing"},
            {"channel_id": "mechanism", "availability": "available"},
        ],
    ),
    CoverageManifest(
        manifest_id="COV:syn-vus", query="Uncertain variant in G1 (synthetic)",
        dataset_version="synthetic-0", retrieved_at=f"{AS_OF}T00:00:00Z",
        generated_by="scripts/build_demo.py@0",
        per_source=[
            {"source": "synthetic variant db", "version": "0", "status": "ok",
             "fetched": 1, "screened": 1},
            {"source": "synthetic functional assays", "status": "unavailable"},
            {"source": "synthetic RNA atlas", "status": "not_queried"},
        ],
        per_channel=[
            {"channel_id": "dna", "availability": "available"},
            {"channel_id": "rna", "availability": "missing"},
            {"channel_id": "mechanism", "availability": "missing"},
        ],
    ),
]

GAPS = {
    "SYN:variant-vus-1": GapResult(
        kind="insufficient_coverage", as_of=AS_OF, entity_id="SYN:variant-vus-1",
        statement=f"No supported route found in the indexed evidence as of {AS_OF}.",
        coverage_manifest_id="COV:syn-vus", known_claim_ids=[],
        failed_sources=["synthetic functional assays (unavailable)"],
        missing_information=[
            "A functional or RNA-level study of this variant",
            "Segregation data from additional families",
        ],
        reviewer_role="clinical geneticist or variant curator",
    ),
    "SYN:disease-e": GapResult(
        kind="hypothesis_only", as_of=AS_OF, entity_id="SYN:disease-e",
        statement=f"Only a hypothesis links Disease E to M1 in the indexed evidence as of {AS_OF}.",
        coverage_manifest_id="COV:syn-a", known_claim_ids=["CLAIM:syn-21"],
        missing_information=["A direct observation of M1 in Disease E"],
        reviewer_role="domain expert",
    ),
}

CONTACT_B = {"label": "Disease B patient group contact page (synthetic)",
             "url": "https://example.invalid/org-b/contact", "source_url": SYN_URL,
             "verified_at": AS_OF}
ASSETS = {
    "SYN:disease-a": [
        AssetResult(
            asset_id="ASSET:syn-registry-b", asset_kind="registry",
            label="Natural-history registry for Disease B (synthetic)", source_url=SYN_URL,
            relevance_claim_ids=["CLAIM:syn-24"], access_conditions="data-access committee",
            status="enrolling (synthetic)", status_source_url=SYN_URL, status_checked_at=AS_OF,
            reuse_limits=["records P1, P2, P5 only; P3-P4 not captured",
                          "Disease B cohort; eligibility rules for Disease A unknown"],
            contact=CONTACT_B, needs_expert_review=["whether shared phenotype fields are comparable"],
            ranking_reasons=["active", "public contact route", "phenotype fields overlap"],
        ),
        AssetResult(
            asset_id="ASSET:syn-cellmodel-b", asset_kind="cell_model",
            label="Cell model for Disease B (synthetic)", source_url=SYN_URL,
            relevance_claim_ids=["CLAIM:syn-25"], access_conditions="material transfer agreement",
            reuse_limits=["different gene (G2 vs G1)", "fibroblast only"],
            needs_expert_review=["whether the M1 assay transfers to Disease A cells"],
            ranking_reasons=["validated M1 assay"],
        ),
    ]
}

CARDS = {
    "SYN:disease-a": [
        ActionCard(
            card_id="CARD:syn-brief-a", kind="evidence_brief", audience="science",
            entity_id="SYN:disease-a", coverage_manifest_id="COV:syn-a",
            this_week="Ask a domain expert to review the shared M1 finding with Disease B.",
            responsible_human="domain expert (reviewer)",
            body_markdown=(
                "**Disease A and Disease B both show decreased M1 activity** in fibroblasts "
                "[^c:CLAIM:syn-12] [^c:CLAIM:syn-14]. One lab-reported result disagrees "
                "[^c:CLAIM:syn-23]. Phenotype overlap is partial [^c:CLAIM:syn-1]. "
                "No RNA-level findings are indexed for Disease A."
            ),
            claim_ids=["CLAIM:syn-1", "CLAIM:syn-12", "CLAIM:syn-14", "CLAIM:syn-23"],
            limitations=["SYNTHETIC demo data", "two descriptions share one experiment (S1)",
                         "not a diagnosis or treatment recommendation"],
            generated_by="template",
        ),
        ActionCard(
            card_id="CARD:syn-outreach-b", kind="outreach_note", audience="family",
            entity_id="SYN:disease-a", asset_ids=["ASSET:syn-registry-b"],
            this_week="Send the Disease B patient group a short note about their registry.",
            responsible_human="family advocate (sends the note)",
            body_markdown=(
                "Hello, we are a Disease A family group. Your registry records phenotypes we also "
                "see [^c:CLAIM:syn-24], and both diseases show a similar change in M1 "
                "[^c:CLAIM:syn-14]. Could we talk about whether your registry design could be "
                "reused?"
            ),
            claim_ids=["CLAIM:syn-14", "CLAIM:syn-24"], contact=CONTACT_B,
            reuse_limits=["registry covers Disease B only"],
            limitations=["SYNTHETIC demo data", "registry fit needs expert review"],
            generated_by="template",
        ),
        ActionCard(
            card_id="CARD:syn-sim-a", kind="simulation_report", audience="science",
            entity_id="SYN:disease-a",
            this_week="Review the simulated plate layout for an M1 assay before booking lab time.",
            responsible_human="lab lead",
            body_markdown=(
                "An illustrative liquid-transfer workflow for the M1 assay was checked in "
                "simulation [^c:CLAIM:syn-25]. It checks the robot's motion and volume "
                "bookkeeping only."
            ),
            claim_ids=["CLAIM:syn-25"],
            limitations=["Workflow simulation only; not wet-lab validated",
                         "biology and hardware not modeled"],
            generated_by="template",
        ),
    ]
}

SUMMARIES = {
    "SYN:disease-a": [
        {"text": "Disease A is associated with phenotypes P1 to P4 in one reviewed study.",
         "claim_ids": PHENO_A},
        {"text": "Two descriptions of one experiment report reduced M1 activity.",
         "claim_ids": ["CLAIM:syn-12", "CLAIM:syn-13"]},
        {"text": "No RNA-level findings are indexed, so that channel shows no data.",
         "claim_ids": []},
    ],
}


def neighbourhood(eid: str, hops: int = 2) -> dict:
    frontier, seen, edges = {eid}, {eid}, {}
    for _ in range(hops):
        nxt = set()
        for c in CLAIMS:
            if c.subject_id in frontier or c.object_id in frontier:
                edges[c.claim_id] = c
                nxt |= {c.subject_id, c.object_id}
        frontier = nxt - seen
        seen |= nxt
    nodes = [{"id": n, "label": BY_ID[n].label, "type": BY_ID[n].type.value}
             for n in sorted(seen) if n in BY_ID]
    return {
        "nodes": nodes,
        "edges": [{"source": c.subject_id, "target": c.object_id, "predicate": c.predicate,
                   "claim_id": c.claim_id, "status": c.status.value,
                   "review_state": c.review_state.value} for c in edges.values()],
        "truncated": False, "omitted": 0,
    }


def scene() -> list[dict]:
    """Box/capsule geoms from robotics/scene.xml, in mm, for the browser replay."""
    out = []
    for g in ET.parse(ROOT / "robotics" / "scene.xml").iter("geom"):
        if g.get("type") != "box":
            continue
        pos = [float(v) * 1000 for v in g.get("pos").split()]
        size = [float(v) * 2000 for v in g.get("size").split()]  # half-size m -> full mm
        out.append({"name": g.get("name"), "pos": pos, "size": size,
                    "collides": g.get("contype", "1") != "0"})
    return out


def simulations() -> dict:
    runs = {}
    for stem, sim_id in (("valid_transfer", "SIM:syn-pass"), ("blocked_path", "SIM:syn-fail")):
        report = json.loads((SIM_DIR / f"{stem}.report.json").read_text())
        traj = json.loads((SIM_DIR / f"{stem}.trajectory.json").read_text())
        runs[sim_id] = {"run_id": sim_id, "label": "recorded run (not live)", "spec": stem,
                        "report": report, "trajectory": traj}
    return {"scene": scene(), "runs": runs}


def dump(model):
    return json.loads(model.model_dump_json())


def build() -> dict:
    return {
        "_synthetic": LABEL,
        "dataset_version": "synthetic-0",
        "as_of": AS_OF,
        "entities": [dump(e) for e in ENTITIES],
        "claims": [dump(c) for c in CLAIMS],
        "connections": {k: [dump(r) for r in v] for k, v in CONNECTIONS.items()},
        "manifests": [dump(m) for m in MANIFESTS],
        "gaps": {k: dump(v) for k, v in GAPS.items()},
        "assets": {k: [dump(a) for a in v] for k, v in ASSETS.items()},
        "cards": {k: [dump(c) for c in v] for k, v in CARDS.items()},
        "summaries": SUMMARIES,
        "graphs": {e.id: neighbourhood(e.id) for e in ENTITIES},
        "simulations": simulations(),
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(ENTITIES)} entities, {len(CLAIMS)} claims")
