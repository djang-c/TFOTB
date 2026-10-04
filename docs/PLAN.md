# AI Rare Disease Atlas: MVP Architecture Validation & Actionable Implementation Plan

Revision: October 3, 2026. This revision replaces the fixed HPO + Reactome + embeddings formula with an extensible multimodal evidence architecture and adds a bounded robotics simulation deliverable. It updates the data model, retrieval and ranking pipeline, upload workflow, automation handoff, acceptance tests, and implementation backlog.

The robotics plan uses MuJoCo for a small simulated liquid-handling workcell, with Gazebo as the alternative if the team already has a ROS 2 stack. This document specifies the work; no simulator or application has been implemented. Earlier claims of validated clinical decisions, guaranteed treatment acceleration, and ready-to-run laboratory scripts are withdrawn; this is a research-support product specification, not a validated clinical system.

## Revision 2026-10-04 (owner decision): automated research, labels instead of review gates

The product exists to remove repetitive research work, so it must run without a human approving each addition. This revision overrides any earlier line in this document that makes human review a condition for finding, storing or displaying evidence.

1. **Research is automated and on demand.** Papers are found by the system (`src/atlas/discovery.py`) from the watched diseases' own ontology names, on a schedule or when a user asks (`scripts/ingest_papers.py --query/--entity`). A human does not have to supply papers. What may run unattended is set once in `config/ingest_policy.json` (live model calls on or off, caps on papers per run and text size, diseases to watch). The caps are the spending control.
2. **Credible sources only.** A paper is accepted only if its own record shows a PubMed-indexed journal article with open-access full text. Preprints, retractions, editorials, expressions of concern and records without a journal are rejected. Every claim cites the paper's real DOI link, taken from the paper's record and never written by a model. Peer review itself is not independently verified here; PubMed indexing of a journal article is the proxy, and the limitation is stated wherever it matters.
3. **Nothing needs human review to be displayed.** Every result carries a label that says where it came from, and the label is the protection:
   - AI-read claim: "found by AI in <article link>; not reviewed by a human".
   - AI hypothesis: "AI hypothesis, not a finding", with the stored claims it was built from.
   - Expert-reviewed: only if a person actually reviewed it. Review is an optional upgrade of the label, never a gate.
4. **The model may make hypotheses** (`src/atlas/hypotheses.py`), always stored as `inference` / `ai_generated` / `unreviewed`. A hypothesis must cite at least two stored claims that are observations from credible sources, may only use entities found in those claims, and uses a hypothesis-only predicate. Hypotheses never count as evidence for another hypothesis and never change an evidence category.
5. **New evidence category:** "literature-supported lead" = observed claims from published or database sources, not expert-reviewed. It ranks just below "reviewed mechanistic lead". Uploads, fixtures, predictions and hypotheses never qualify.
6. **Unchanged, because it is what makes unattended runs trustworthy:** the quote must appear verbatim in the paper; types and names must resolve (unresolved stays unresolved); stored claims are immutable and conflicts are quarantined; no combined score and no probability; missing is not zero; no dosing, prescribing or eligibility language; private cases never enter the public store.
7. **Licences:** this is a hackathon project, not a commercial use; any open-access paper is accepted and its licence is recorded per paper. Revisit before any commercial or redistribution use.

## Problem statement and challenge alignment

The supplied Hack-Nation Challenge 05 brief asks for an evidence-backed journey from an isolated diagnosis to a meaningful connection, an existing research asset, a collaborator, and a concrete next step. Its primary user is Maria, a patient-group leader; Devon, Priya, and Dr. Osei represent caregiver, therapeutic scouting, and research use cases.

The product problem is not simply finding similar disease names. We need to show which connections are supported, which are speculative, which have contrary evidence, and which assets might actually be reusable. A broad mechanism hypothesis and a shared patient registry must not be mistaken for proof that two diseases should receive the same treatment.

| Challenge expectation | Revised solution | Validation still required |
|---|---|---|
| Meaningful graph, defensible clusters, counterexamples | Typed biological and research-network graph; multimodal comparison; explicit contradictory and missing evidence | Expert review of selected connections and negative controls |
| Sourced claims with uncertainty | Claim-level provenance, quotes, review status, evidence context, and prediction labels | Citation entailment and identifier audit |
| Patient progress | Connection explanation plus asset, public contact, and scoped research-action card | User can explain the connection and its limits |
| Meaningful 10× milestone | Measure time to a quality-checked collaboration/evidence brief | Establish baseline and include human review time |
| Understandable experience | Summary-first interface with evidence channels on demand | Family-facing comprehension test |
| OpenAI use for track eligibility | Extraction, reconciliation suggestions, and grounded explanation | Verify actual model/tool use and reproducibility |

These are design alignments to the uploaded brief, not claims that the MVP has passed scientific or judging validation.

## Goals

- **Useful discovery:** For a seeded disease, surface at least one connection with a clear evidence label (expert-reviewed where a person has reviewed it, otherwise literature-supported or labelled hypothesis), a relevant asset, and a contact route, or an explicit evidence gap.
- **Explainable matching:** Every displayed connection exposes contributing evidence channels, missing channels, contradictions, and source-backed claims.
- **Extensibility:** Add a new evidence-channel implementation without rewriting the graph schema, result contract, or UI.
- **Bounded personalization:** Demonstrate matching a synthetic individual's phenotype and selected variant annotations to research evidence without publishing case data.
- **Inspectable automation:** Connect one evidence-backed research question to a human-approved demo specification, simulated robot motion, logical resource checks, and an exported test report.
- **Measurable acceleration:** Benchmark the research-brief milestone against a manual baseline, reporting quality and reviewer effort alongside elapsed time.

## Non-goals

- **Clinical decisions:** No automated diagnosis, prescribing, dose recommendation, therapeutic eligibility determination, or patient-specific treatment selection.
- **Raw sequencing analysis:** No FASTQ/BAM processing, variant calling, whole-genome embeddings, or raw RNA-seq processing in the hackathon MVP.
- **Clinical-grade patient system:** No real patient uploads in the demo. Synthetic examples are clearly labeled and isolated from public research claims.
- **All-disease completeness:** Support rare and common diseases structurally, but curate one small, evidence-rich slice first.
- **Autonomous experiments:** No physical robot execution, automatic experimental dispatch, fluid-dynamics validation, or simulated biological efficacy. The robot demo models motion and workflow constraints only.

## User stories

- **Maria, P0:** As a patient-group leader, I want to see why another community is relevant and what existing asset we might reuse, so I can approach a partner with a sourced proposal.
- **Dr. Osei, P0:** As a researcher, I want to compare variant, RNA, mechanism, and assay evidence separately, so I do not mistake shared symptoms for shared biology.
- **Devon, P0:** As a caregiver, I want an understandable explanation of what is known and missing, so I can discuss research options without receiving an unsupported treatment recommendation.
- **Research contributor, P0:** As an investigator uploading a finding, I want it linked to the right entities with attribution and an unreviewed label, so others can discover it without mistaking it for established evidence.
- **Lab researcher, P0:** As a researcher reviewing a proposed experiment, I want to inspect a simulated handling sequence and see setup failures before any hardware execution, so I can assess the workflow rather than trust an unchecked generated script.
- **Priya, P1:** As a therapeutic scout, I want to filter research leads by mechanism direction and tissue context, so I can prioritize expert assessment.
- **Case reviewer, P1:** As an authorized reviewer, I want a synthetic case's phenotype and variants matched together, so I can demonstrate individualized research discovery without exposing a genome.

## Requirements and architecture

### Architectural decision

Replace the fixed formula with:

```text
Public structured records + permitted literature + researcher findings
                         |
          Deterministic parsers / bounded LLM extraction
                         |
       Identifier resolution + claim and context validation
                         |
           Versioned public evidence graph + claim store
                         |
    Candidate union across pluggable evidence channels
                         |
     Channel-specific comparison + compatibility checks
                         |
   Evidence-qualified ranking + separate asset/collaborator ranking
                         |
      Explainable paths + optional community visualization
                         |
          Human-reviewable "next step this week" cards
                         |
          Approved demo experiment specification
                         |
      Workflow checks + MuJoCo motion simulation
                         |
       Recorded execution trace + scoped validation report

Synthetic/private case store --> scoped case-to-research queries
                          (never copied into the public graph)
```

Symptoms are already part of phenotype representation: HPO provides an ontology of phenotypic abnormalities and supports information-content-based comparison. That does not make phenotype similarity sufficient to establish a molecular explanation ([HPO foundational paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC2668030/)).

RNA evidence adds a distinct layer: observed abnormal splicing can connect genomic variants to transcript effects, while tissue availability, batch effects, and secondary findings limit interpretation ([rare-disease transcriptomics review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10516351/)). The architecture therefore models evidence along a chain rather than treating a whole DNA or RNA strand as one similarity vector:

```text
Variant -> transcript consequence -> RNA/protein effect
        -> cellular mechanism -> phenotype
```

Each arrow is a separate claim. A missing or inferred arrow remains visible; a complete-looking path must not silently convert correlation into causation.

### Evidence channels

All rows below specify proposed product behavior. P0 channels use curated or preprocessed records, not new predictive model training.

| Channel | Inputs and comparison | Required context | Priority |
|---|---|---|---|
| Symptoms and clinical course | HPO semantic similarity plus separate onset/progression comparisons | Present, explicitly absent, or unknown; onset, severity, frequency, annotation source | P0: HPO and missingness; P1: richer temporal comparison |
| DNA variants and inheritance | Exact normalized variant matches, related variants, documented functional effects; gene match shown separately | Genome assembly, transcript version, alleles, zygosity, phase/inheritance when known | P0: curated annotations; P1: synthetic case matching |
| RNA and transcript effects | Observed or predicted splicing changes, expression direction, transcript-specific effects | Tissue/cell type, assay or predictor, comparator, effect direction, quality metadata | P0: published/preprocessed findings; P1: numeric signatures |
| Molecular mechanisms | Effect direction, protein roles, pathways, cell types, documented mechanism claims | Variant scope, tissue, evidence status, causal vs associative wording | P0 |
| Experimental findings | Comparable assay phenotypes, rescue results, null/negative results | Model, assay, controls, intervention, units, dose/time context when applicable | P0: structured findings; P1: quantitative comparison |
| Proteomic/metabolic evidence | Protein abundance/activity, metabolite patterns and functional signatures | Specimen, platform, normalization and comparator | P2 extension |
| Literature semantics | Embeddings retrieve candidate papers/entities missed by exact terminology | Index version, source span, model version | P1 retrieval aid, not proof |
| Research assets and networks | Shared models, registries, investigators, studies, public contact routes | Access conditions, current status, species/tissue, reuse limits | P0, ranked separately from biology |

For the proposed phenotype implementation, estimate information content from a pinned, broader disease-annotation corpus, not just the tiny demo cluster. Record the corpus and ontology versions; avoid double-counting ancestor terms. A missing feature is unknown unless a source explicitly reports its absence.

For RNA comparison, the MVP should ingest structured findings such as “aberrant splicing observed in tissue X” rather than comparing arbitrary raw expression values across studies. Cross-study numeric signature matching remains disabled until preprocessing and comparability rules are specified.

### Graph schema and identity

Use NetworkX `MultiDiGraph` as the MVP query projection and SQLite plus versioned JSON artifacts as the persistent source of truth. Neo4j is a possible later adapter, not a second hackathon dependency. Performance must be measured rather than assumed.

| Entity | Proposed identity representation |
|---|---|
| Disease | Verified MONDO identifier; preserve source cross-references |
| Gene | Verified HGNC identifier and symbol; retain Ensembl/NCBI cross-references |
| Variant | Normalized representation with assembly and alleles; transcript-versioned HGVS and source identifiers where available |
| Transcript | Versioned RefSeq or Ensembl accession; retain genomic orientation and coordinate mapping |
| Protein | Stable protein accession mapped explicitly to gene/transcript |
| Phenotype | Verified HPO identifier plus observation qualifiers |
| Mechanism / pathway | Curated mechanism record; Reactome or GO reference where appropriate |
| RNA / assay finding | Internal finding ID linked to sample/model, method, source, and relevant entities |
| Drug / chemical | Verified ChEBI or other appropriate external identifier |
| Study / registry / model / organization | Registry or source-specific ID; official URL and access/status metadata |
| Claim / evidence item | Immutable internal ID, source span, provenance, version |
| Synthetic/private case | Separate scoped case ID; not a public graph identifier |

Do not generate namespace-shaped IDs from labels: for example, a symbol appended to `HGNC:` is not a validated HGNC identifier. Unresolved identities remain unresolved, with candidates presented for review.

Represent predicates such as `AFFECTS_TRANSCRIPT`, `ASSOCIATED_WITH_PHENOTYPE`, `HAS_OBSERVED_RNA_EFFECT`, `HAS_PREDICTED_RNA_EFFECT`, `PERTURBS_MECHANISM`, `SUPPORTED_BY`, `CONTRADICTED_BY`, `INVESTIGATED_IN`, and `ASSET_RELEVANT_TO`. Permit strong causal predicates only when the supporting evidence justifies that exact claim.

### Claims, provenance, and confidence

Replace the old single four-tier hierarchy with independent dimensions. Publication type, observation status, methodological quality, and clinical relevance are not interchangeable.

Every claim must record:

- **Identity:** Claim ID, normalized subject and object IDs, allowed predicate, and schema version.
- **Evidence:** Source URL/record identifier, quoted span or structured source field, publication and retrieval dates, and extraction method.
- **Status:** `reported_observation`, `computational_prediction`, or `inference`; publication/source type; review state; source-reported classification where relevant.
- **Context:** Organism, tissue/cell type, transcript/variant scope, assay/model, effect direction, and experimental conditions when applicable.
- **Uncertainty:** Contradicting claim IDs, applicability limits, missing fields, and review notes.
- **Lineage:** Original study/experiment grouping and derivation links, so repeated descriptions of one experiment are not counted as independent confirmation.
- **Scores:** Extraction score or source-provided predictor score only with a documented meaning and version. Use `null` when unavailable; never label an LLM's numeric confidence as probability of causality or treatment success.

New uploads remain `lab_reported` and `unreviewed` even if they resemble existing publications. A reviewer can record corroboration without erasing the original source type or accepting every claim in the upload.

### Retrieval, compatibility, and ranking

Use a staged pipeline rather than one opaque weighted sum.

1. **Resolve the query.** Identify whether it is a disease, gene, variant, symptom, mechanism, organization, or synthetic case. Ask for clarification if identity or assembly is ambiguous.
2. **Retrieve a candidate union.** Each available channel retrieves candidates independently. Combine and deduplicate them; do not require a candidate to pass all channels.
3. **Calculate a comparison vector.** Return one result per channel with score, availability, supporting claims, conflicts, and caveats.
4. **Apply claim-specific compatibility checks.** Flag opposite functional directions, tissue mismatch, uncertain inheritance compatibility, incompatible assays, or unsupported variant-to-mechanism steps.
5. **Assign evidence categories.** Proposed labels: “reviewed mechanistic lead,” “symptom-level lead,” “hypothesis only,” “conflicting evidence,” and “insufficient coverage.” Labels apply to the scoped connection, not an entire disease.
6. **Rank within categories.** For the MVP, prefer direct, reviewed, relevant-context evidence and show the comparison vector. Use configurable tie-breakers rather than claiming a calibrated overall probability.
7. **Rank actions separately.** Asset access, contact validity, active status, and applicability determine practical next steps; they do not raise biological confidence.

Critical rules:

- **Missingness:** Missing RNA data is not a zero similarity score, and a phenotype-only candidate cannot be displayed as fully supported through automatic reweighting.
- **Directionality:** “Same gene” is not synonymous with “same mechanism.” Opposing effects should block an unsupported shared-treatment inference while preserving potentially useful research connections.
- **Dependency:** DNA, RNA, and phenotype descriptions from one study count as connected evidence, not three independent replications.
- **Novel findings:** Keep an exploratory hypothesis view so new but uncorroborated observations are discoverable without being promoted to established findings.
- **Common disease support:** Use the same schema for rare and common diseases, but label the scope of each association. Do not treat a population-level association as proof of an individual's causal variant.

No default `0.45/0.35/0.20` weighting survives this revision. Any future combined score requires a documented evaluation set, missing-data policy, task-specific calibration, and versioned parameters.

### Pluggable channel contract

The following is an illustrative interface specification, not implemented or validated production code:

```python
class EvidenceChannel:
    channel_id: str
    version: str
    required_fields: tuple[str, ...]

    def retrieve_candidates(self, query, context):
        """Return candidate IDs and retrieval provenance."""
        raise NotImplementedError

    def compare(self, query, candidate, context):
        """Return a ChannelComparison record; preserve missingness."""
        raise NotImplementedError
```

Required `ChannelComparison` fields:

```text
channel_id, channel_version, query_id, candidate_id
availability: available | missing | incompatible | failed
score: number or null
score_definition: explicit method, not "confidence"
supporting_claim_ids[]
contradicting_claim_ids[]
context_matches[]
context_mismatches[]
missing_fields[]
limitations[]
```

A `ConnectionResult` groups channel comparisons, evidence category, compatibility flags, path claim IDs, coverage manifest ID, and separate asset/collaborator results. The explanation generator receives these records, not unrestricted access to invent missing biological steps.

### Optional clustering

Leiden is an optional organization layer after evidence qualification, not the definition of similarity. Run it only on a documented projection with declared edge eligibility and weights; preserve individual multi-evidence paths in the underlying graph.

A disease may participate in several mechanism views. Community membership must not imply a shared treatment or force the product to hide a relevant connection across cluster boundaries. Cut clustering before cutting provenance, counterexamples, or useful action cards.

### Individualized research matching and privacy

The proposed case flow is: structured phenotype observations plus selected, normalized variant annotations, with optional preprocessed RNA findings. The output is relevant research, evidence gaps, and questions for an expert, not a diagnosis or genome-targeted treatment.

Phenopackets provides a standard for representing individual clinical and phenotypic data and can link to genomic information; it does not itself validate diagnostic matching ([GA4GH Phenopackets](https://www.ga4gh.org/product/phenopackets/)).

- **Demo:** Synthetic case fixtures only; no patient identifiers, real genomes, or automatic patient matching across organizations.
- **Isolation:** Case storage and derived results stay outside the public graph and public search index. Upload processing must not silently convert a case observation into a public research claim.
- **Future deployment:** Require appropriate consent, access controls, audit logs, retention/deletion policy, and review of external model-provider data handling before accepting real genomic data. Genomic data sharing requires appropriate consent or authorization and governance, including restrictions on downstream uses ([GA4GH consent policy](https://www.ga4gh.org/product/consent-policy/)).
- **Personalized treatment:** Keep outside MVP scope. A reported individualized editing success does not make general treatment selection automatic; the NIH's single-infant CPS1 example explicitly required long-term safety and effectiveness follow-up ([NIH report](https://www.nih.gov/news-events/nih-research-matters/infant-rare-disease-receives-customized-gene-therapy)).

### Ingestion and upload workflow

Prefer deterministic parsing for structured source records. Use OpenAI extraction for bounded text passages, proposed entity reconciliation, and plain-language explanations. Pin the selected model, prompt, schema, and source snapshots; confirm model availability during implementation instead of hard-coding an unverified model choice here.

For every connector, first verify access, terms/licensing, fields, rate limits, and update behavior. Candidate sources remain ClinVar, HPO, MONDO, HGNC, permitted PubMed/PMC content, Reactome, ClinicalTrials.gov, NIH RePORTER, and official organization/model-provider pages; none is assumed to provide unrestricted bulk content.

Upload processing:

1. Accept a structured finding or permitted research text, not real patient records.
2. Capture contributor attribution, sharing permission, source type, method, tissue/model, and positive/null/negative result.
3. Extract candidate claims and resolve IDs against pinned mappings.
4. Validate quoted support and return unresolved identities or missing metadata for correction.
5. Quarantine malformed records and treat uploaded instructions as data, never as system instructions.
6. After contributor confirmation, expose eligible findings with visible `lab_reported/unreviewed` labels; queue expert review for strong mechanism claims.
7. Recompute affected channel comparisons while preserving previous graph and ranking versions.

### Coverage and honesty

Create a coverage manifest for every search: query, source versions, retrieval date, filters, fetched/screened counts, and failed or unavailable sources. Counts must come from recorded operations, not generated text.

Use “No supported route found in the indexed evidence as of [date]” rather than “No treatment/registry exists.” Distinguish:

- **Insufficient coverage:** Required sources or channels were not available.
- **Unresolved identity:** The query cannot yet be mapped reliably.
- **Hypothesis only:** A candidate exists without sufficient direct support.
- **Conflicting evidence:** Relevant claims disagree.
- **Supported research route:** Evidence supports a scoped next investigation, not necessarily a therapy.

Each gap card identifies what information could change the result and who should review it. It must not fabricate an experiment or assert that any one assay will resolve the uncertainty.

## Action layer and automation boundaries

| Workstream | Proposed automation | Required human boundary | Priority |
|---|---|---|---|
| Variant-to-mechanism evidence | Assemble normalized annotations, cited functional evidence, predictions, and missing steps | Expert interprets mechanism; no automatic loss/gain-of-function treatment routing | P0 evidence card |
| Existing models and registries | Retrieve assets; compare model/tissue/assay scope and access conditions | Asset owner confirms suitability and access | P0 |
| Researcher collaboration | Explain overlap; draft a sourced outreach note to a verified public contact | User reviews and sends | P0 |
| Repurposing research | Present reviewed drug-target-mechanism paths and unresolved safety/applicability questions | No prescribing, doses, or claim that off-label use is safe | P1 |
| ASO program preparation | Show a dated criteria checklist and draft missing-information summary | Program and research physician determine eligibility and suitability | P1 |
| Registry harmonization | Map synthetic fields to phenotype terms; export a validated example schema | No claim of regulatory-grade data or automatic approval of a registry | P1 |
| Funding opportunities | Match topics and verified active notices | Verify deadline and eligibility before displaying “apply” | P2 |
| Robotics workflow simulation | Compile one reviewed demo specification to logical resource checks and MuJoCo motion; export a trace/report | No real fluids, biological validation, or physical execution | P0 bounded demo; P1 Opentrons adapter |

AlphaMissense is not validated or approved for clinical use according to its maintainers, so its predictions must not be presented as an autonomous therapeutic router ([AlphaMissense repository](https://github.com/google-deepmind/alphamissense)). RNA/splicing predictions likewise require context and do not alone establish causality ([transcriptomics review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10516351/)).

For ASO program preparation, verify current program criteria rather than inferring eligibility from a score or database record count; n-Lorem describes requirements involving diagnosis, defined genetic cause, location, and a qualified research physician/institution ([n-Lorem qualifications](https://www.nlorem.org/patients/qualifications-for-treatment/)). Do not equate the number of ClinVar submissions with the worldwide number of patients.

The earlier robot code example is removed because repeated dispensing from one source did not implement the serial dilution described in its comments. No replacement is certified here; even Opentrons simulation has explicit limitations, such as liquid-presence checks always succeeding in simulation ([Opentrons API reference](https://docs.opentrons.com/v2/new_protocol_api.html)).

## Robotics simulation deliverable

### Decision and limits

Use MuJoCo by default for an illustrative gantry/pipette workcell with a reagent source, tip location, waste location, and 96-well plate. Model a small subset of wells and one fixed handling sequence; do not attempt a complete autonomous laboratory.

MuJoCo supports articulated-body simulation, contacts, visualization, and model descriptions, but its documentation does not establish validation against a physical laboratory system ([MuJoCo overview](https://mujoco.readthedocs.io/en/stable/overview.html)). The proposed scene is therefore a generic workcell, not a certified digital twin of an Opentrons robot.

Gazebo is the alternative when existing robot descriptions, controllers, and ROS 2 experience make integration easier; its documented ROS 2 bridge exchanges supported message types between the simulator and ROS ([Gazebo ROS 2 integration](https://gazebosim.org/docs/latest/ros2_integration/)). Choose one engine at the initial technical spike, record the version, and do not build both.

### Evidence-to-simulation flow

```text
Graph connection and unresolved research question
    -> evidence-linked ExperimentProposal (draft)
    -> human confirms scope, model relevance, and demo assumptions
    -> ExperimentSpec (versioned)
    -> deterministic workflow compiler
    -> logical checks: labware, volumes, tips, operation ordering
    -> MuJoCo trajectory generation and modeled collision checks
    -> execution trace + video + pass/fail/unsupported report
    -> graph-linked SimulationRun record, explicitly not biological evidence
```

An optional second backend compiles the same specification to a pinned Opentrons protocol and invokes its simulator. That is a separate adapter, not an automatic translation of MuJoCo trajectories or proof that physical hardware can execute them.

### Minimum scene and workflow

The first demonstration should represent plate preparation for a proposed assay using simulated liquids only. Select the actual scientific question after evidence review; the handling simulation is not itself an assay and must not fabricate cell viability, molecular response, or treatment results.

- **Scene:** Fixed deck, one virtual three-axis pipette carriage, one source, virtual tips, waste, and one destination plate. Document simplified geometry and collision bodies.
- **Sequence:** Inspect setup, acquire a logical tip, move to source, record a modeled aspirate, move to a target well, record a modeled dispense, and dispose of the tip. Repeat only for a small fixed well set.
- **Resource ledger:** Track source/destination volume, pipette capacity, tip availability, and operation state. Units and capacity checks must be explicit.
- **Motion checks:** Evaluate the modeled path for prohibited contacts and workspace-limit violations. Whitelist intended approach regions instead of calling every contact a collision.
- **Failure demonstration:** Deliberately supply insufficient modeled source volume or an obstructed path. Show the rejected operation, reason, and correction.
- **Replay:** Provide a deterministic rerun from the saved specification; label any recorded video as a replay, not live simulation.

Use a simple transfer workflow before adding serial dilution. If dilution is later included, derive and test the concentration/volume bookkeeping separately and require wet-lab review; an animation must never stand in for those checks.

### Required schemas and outputs

`ExperimentProposal` carries source claim IDs, the research question, proposed assay/model, unresolved biological assumptions, and reviewer state. `ExperimentSpec` carries an immutable proposal reference, illustrative labware geometry, robot model/version, sequence of typed operations, units, logical liquid inventory, virtual tip policy, and allowed operating bounds.

`SimulationRun` must record:

```text
run_id, experiment_spec_hash, scene_hash
simulator_name, simulator_version, adapter_version, random_seed
review_state, started_at, finished_at
operation_trace[], ledger_before, ledger_after
checks[]: check_name, status(pass|fail|not_modeled), reason
modeled_collision_events[], failures[]
simulation_time, wall_clock_time
report_path, replay_path
scope_label: "Workflow simulation only; not wet-lab validated"
```

Record a `SimulationRun` as an engineering artifact linked by `SIMULATES_WORKFLOW_FOR`, not an assay result or evidence that a disease mechanism is correct. Simulation success must not raise biological similarity, claim confidence, or drug ranking.

Planned deliverable files, not files already built:

```text
robotics/
  scene.xml
  experiment_spec.schema.json
  fixtures/valid_transfer.json
  fixtures/insufficient_volume.json
  fixtures/blocked_path.json
  compile_workflow.py
  simulate.py
  tests/
  README.md
demo_outputs/
  simulation_report.json
  simulation_report.md
  simulation_replay.mp4
```

The simulator should run locally with pinned dependencies and a documented command. The web prototype can show the trace, report, and recorded replay; live browser interaction with MuJoCo is not a P0 dependency. If simulation cannot be reproduced, disclose that and do not substitute an animation labeled as a successful simulation.

### Validation boundaries

| Layer | What a passing check means | What it does not establish |
|---|---|---|
| Specification | Required fields, units, and declared equipment are internally consistent | The scientific design is useful |
| Logical workflow | Declared resources and operation order satisfy the implemented rules | Real liquid volumes, sterility, or pipetting accuracy |
| MuJoCo | The modeled trajectory passes selected geometry/dynamics checks | Safe operation on a real robot, calibration, or real-world cycle time |
| Optional Opentrons adapter | The pinned protocol simulator accepts the generated protocol under its rules | Physical liquid detection or experimental success |
| Biology | Not modeled; report `not_modeled` | Drug activity, rescue, efficacy, safety, or cure |

Require a lab expert to review any future physical protocol, hardware-specific calibration, liquid handling, contamination controls, and experimental design separately. No hardware endpoint or experiment-ordering connector belongs in this MVP.

## Implementation plan

### Technical defaults

- **Backend:** Python, FastAPI, typed validation models, deterministic ingestion jobs, and isolated extraction workers.
- **Persistence:** SQLite claim/source tables and versioned JSON snapshots; NetworkX graph projection.
- **Similarity:** Channel registry and explicit comparison results. Pinned ontology/annotation data; precomputed small-fixture comparisons.
- **Frontend:** React with a search-first interface, evidence drawer, optional graph canvas, and Markdown action export.
- **AI:** OpenAI-backed structured extraction and grounded explanations; cache results and label cached/replayed output accurately.
- **Robotics:** MuJoCo with a generic scene, deterministic operation compiler, separate liquid/tip ledger, and reproducible report/replay. Gazebo substitutes only if an existing ROS 2 setup justifies the change.
- **Testing:** Unit tests for identity, context, missingness, ranking gates, upload quarantine, and public/private separation.

### Dataset and research scope

Proposed seed target: 6–10 diseases, 10–20 curated variant/transcript findings, 20–40 claim-bearing source passages, 5–10 assets/organizations, and 2 synthetic cases. These are workload targets, not counts already collected.

Start by auditing one candidate disease cluster, such as lysosomal/neurodegenerative disorders, rather than assuming every named condition shares a usable mechanism. Include one common-disease connection only if evidence review supports the exact relationship; otherwise show an explicit gap and retain common-disease schema support.

The fixture must contain a useful positive route, a symptom-only connection, an opposing-mechanism example, a missing-RNA case, an uncertain variant, a contradictory finding, and a no-route result. Biological examples require cited expert review; synthetic examples are reserved for software behavior tests and labeled accordingly.

### Actionable backlog

Effort labels describe relative scope, not guaranteed duration. Owners are suggested roles, not assigned people.

| ID | Task / owner | Priority | Depends on | Deliverable and done condition |
|---|---|---|---|---|
| T01 | Audit cluster and sources / Science | P0 | None | Verified positive route, counterexample, asset/contact; access and license manifest |
| T02 | Define entities, claims, context, coverage / Backend | P0 | T01 draft | Versioned schemas and valid/invalid fixtures |
| T03 | Build deterministic ID resolver / Data | P0 | T02 | Stable IDs resolve; ambiguous variants and transcript versions are not silently merged |
| T04 | Build source ingestion and bounded extraction / Data + AI | P0 | T02–T03 | Source-linked claims with quoted support and quarantined failures |
| T05 | Implement channel interface and comparison contracts / Backend | P0 | T02 | New mock channel registers without core schema/UI changes |
| T06 | Implement phenotype comparison / Data | P0 | T03, T05 | Versioned IC inputs; symptom polarity and missingness tests pass |
| T07 | Implement curated DNA/RNA/mechanism comparison / Data + Science | P0 | T04–T05 | Separate reported/predicted effects and explicit tissue/direction conflicts |
| T08 | Implement structured assay finding channel / Data | P0 | T04–T05 | Positive/null/negative findings retain model, assay, and evidence lineage |
| T09 | Implement candidate union and evidence gates / Backend | P0 | T06–T08 | Channel vectors, categories, conflicts, and separate coverage returned |
| T10 | Implement asset/contact action cards / Product + Backend | P0 | T01, T09 | Every card includes evidence path, reuse limits, contact, next step, and reviewer |
| T11 | Build upload quarantine/review flow / Backend + UI | P0 | T02–T04 | Lab report stays unreviewed; attribution and claim-level review preserved |
| T12 | Build explorer and evidence inspector / Frontend | P0 | T02 mock; T09 integration | Summary-first journey, per-channel explanation, honest gap view |
| T13 | Run evaluation and repair errors / Science + QA | P0 | T09–T12 | Signed-off fixture report; critical negative cases pass |
| T14 | Package prototype, reproduction README, video / Team | P0 | T13 | Working demo, repo, data manifest, team video and one-minute walkthrough |
| T15 | Add synthetic case-to-research matching / Backend | P1 | T03, T09 | Case remains private; output is research evidence, not a diagnosis |
| T16 | Add semantic retrieval / AI | P1 | T04, T09 | Embedding-only candidates remain hypotheses without supporting claims |
| T17 | Add ASO/repurposing/harmonization drafts / Product + Science | P1 | T10, T15 | Expert-review boundaries and missing criteria displayed |
| T18 | Add Leiden visualization / Data + UI | P2 | T09, T13 | Projection/version documented; clusters do not imply treatment equivalence |
| T19 | Add further omics channel / Data | P2 | T05, T13 | Comparability and missing-data rules specified before ranking |
| T20 | Freeze demo experiment/robotics contracts / Automation + Science | P0 | T02; T10 for final binding | Approved illustrative sequence, safety boundaries, no invented biology |
| T21 | Build scene and workflow compiler / Automation | P0 | T20 | Fixed scene and typed operations execute reproducibly |
| T22 | Add resource ledger and failure gates / Automation + QA | P0 | T20–T21 | Valid transfer passes; insufficient volume and blocked path fail |
| T23 | Export run report, replay, graph-linked artifact / Automation + UI | P0 | T10, T21–T22 | Evidence-linked demo shows scoped checks and “not wet-lab validated” |
| T24 | Add Opentrons simulator adapter / Automation | P1 | T20–T23 | Same spec produces a pinned, tested protocol; simulator limits disclosed |

### Proposed 24-hour sequence

Assumption for the expanded scope: four available contributors covering data/science, backend/AI, frontend/product, and robotics, with access to a qualified evidence reviewer. This is a schedule proposal, not a delivery guarantee; with fewer contributors, extend the schedule or explicitly reduce scope rather than silently dropping the requested robotics deliverable.

| Window | Atlas track | Robotics track | Exit gate |
|---|---|---|---|
| Hours 0–3 | T01–T02; mock UI contract | Simulator spike; T20 draft | One sourced route and counterexample; scene can load |
| Hours 3–7 | T03–T05; frontend fixtures | T21; independent illustrative spec | Claims persist; minimal modeled motion works |
| Hours 7–12 | T06–T09; evidence inspector | T22 ledger and failure checks | Inspectable evidence channels; valid/invalid runs separated |
| Hours 12–16 | T10–T12 | Final T20 evidence binding; T23 | Search-to-action journey links to a reviewed demo spec |
| Hours 16–20 | T13; T15 only if stable | Reproducibility and integration tests | Biological and engineering negative tests pass |
| Hours 20–24 | T14; benchmark/disclosure | Package replay/report and local run | Prototype, simulator, and submission reproducible |

Cut in order: optional Opentrons adapter, richer omics, clustering, embeddings, extended ASO/repurposing features, then synthetic case UI. Preserve claim provenance, curated DNA/RNA evidence, channel-level explanation, a useful action, negative cases, and the bounded simulation/report. If robotics slips, simplify geometry and use a local run with recorded replay instead of building live web control; do not claim physical validation.

## Success metrics and acceptance tests

### Release checks

These are proposed acceptance targets. No results have been measured yet.

| Test | Given / when / then |
|---|---|
| Evidence integrity | Given a displayed edge, when inspected, then its claim, source span, context, status, and contradictions are accessible |
| Symptoms | Given specific and broad phenotype matches, when ranked, then the selected IC method is applied reproducibly and its corpus is disclosed |
| Missing RNA | Given no RNA record, when compared, then RNA is `missing` with null score, not a mismatch or confirmation |
| Mechanism conflict | Given reviewed opposing effects, when considering a shared-treatment path, then the unsupported inference is blocked and the conflict remains visible |
| Uncertain variant | Given a variant without functional evidence, when explained, then no definitive effect or therapeutic modality is invented |
| Tissue mismatch | Given an RNA result from a different tissue, when compared, then its applicability caveat is retained |
| Duplicate evidence | Given two papers reporting the same experiment, when summarized, then they do not count as independent replication |
| Assay incompatibility | Given unlike assay contexts, when compared, then numeric values are not pooled without a documented transformation |
| Upload review | Given an unreviewed finding, when it resembles a published claim, then it does not auto-promote to established evidence |
| Extension | Given a test-only channel, when registered, then its result appears through the common contract without core rewrites |
| Private case | Given a synthetic/private case, when public graph/search endpoints are called, then case data and derived private associations are absent |
| Honest gap | Given no supported path or a failed source, when searched, then the result discloses coverage and missing evidence rather than asserting global absence |
| Action traceability | Given an action card, when reviewed, then each biological justification maps to evidence and the next step has a responsible human |
| Simulation traceability | Given a simulation run, when opened from the graph, then its experiment-spec hash, source claims, model version, and review state are inspectable |
| Resource failure | Given insufficient modeled source volume or exhausted tips, when compiled, then the operation is rejected with an explicit reason |
| Motion failure | Given an obstructed modeled path or out-of-range target, when tested, then the report records failure rather than silently clipping motion |
| Engineering/biology separation | Given a passing simulation, when rankings refresh, then no biological claim or treatment confidence is increased |
| Simulator reproducibility | Given a pinned scene/spec/environment, when rerun, then operation outcomes and checks agree within documented numeric tolerances |
| Honest simulation limits | Given any simulation report, when displayed, then biological outcomes are `not_modeled` and physical validation is explicitly absent |

Target 100% provenance completeness on displayed demo claims and zero critical privacy, unsupported-treatment, or invented-citation failures in the fixture suite. Have a reviewer audit every positive demo path and counterexample; report the small evaluation size explicitly rather than claiming population-level accuracy.

Measure query latency on the seeded dataset with a provisional target of p95 under two seconds for cached graph results; measure live extraction separately. Record channel coverage, review corrections, unmapped IDs, user task completion, and whether users can distinguish observations from hypotheses.

### The 10× hypothesis

Use a narrow milestone: produce a reviewer-accepted collaboration/evidence brief containing a supported connection, reusable-asset assessment, contact route, and unresolved questions. Do not compare a computational shortlist with a completed trial or approved treatment.

Measure manual and Atlas-assisted completion of comparable tasks, including source verification, reviewer corrections, and failed attempts. Use multiple tasks and counterbalanced ordering where feasible; disclose sample size, reviewer expertise, setup time, and seed-curation effort.

Compute speedup as manual time divided by assisted time for briefs meeting the same quality rubric. Report measured values and assumptions; if the result is not 10×, state that. The previous “years to months” and instantaneous therapeutic triage claims are removed because they were not established by an evaluation.

## Demo and submission

Proposed one-minute walkthrough:

- **0–15 seconds:** Maria searches a disease or synonym and sees a short explanation of the available evidence.
- **15–30 seconds:** Open a related disease and inspect distinct phenotype, DNA/RNA, and mechanism evidence; expose a limitation or counterexample.
- **30–45 seconds:** Find an existing research asset and collaborator; open the evidence-linked demo experiment and a short labeled simulation replay.
- **45–60 seconds:** Show a checked workflow or deliberate failure, then export the research-action brief with biological uncertainties and simulation limits.

Prepare the working prototype, source repository, README, dataset reproduction manifest, team video, and one-minute walkthrough requested in the uploaded brief. Add the runnable simulator scene/scripts, valid and failing fixtures, report, and replay; keep a longer robotics demonstration available outside the one-minute journey. Include a limitations panel and clearly label synthetic records, cached AI output, unreviewed uploads, recorded simulation, and optional unimplemented features.

## Open questions

| Question | Owner | Blocking? | Default |
|---|---|---|---|
| Which cluster has a complete, defensible route and counterexample? | Science | Yes, before data freeze | Choose evidence completeness over disease count |
| Who reviews biological claims? | Team lead | Only for the “reviewed” label; no longer needed to display | Display AI-found claims and AI hypotheses with their labels; disclose the absence of expert review |
| Which sources permit the planned use and storage? | Data lead | Yes per connector | Use permitted cached records or omit source |
| What tissue/context rules are appropriate for each comparison? | Science + Data | Yes per numeric channel | Use categorical claims with caveats |
| Are real individual genomes in scope? | Product | No for this MVP | No; synthetic cases only |
| What overall ranking weights are justified? | Science + Data | No | Evidence categories and inspectable vectors; no clinical probability |
| Does the team already have a ROS 2 stack that favors Gazebo? | Automation | Yes, at initial spike | MuJoCo unless existing tooling justifies Gazebo |
| Who can own the robotics track within the hackathon window? | Team lead | Yes for the proposed schedule | Assign a fourth contributor or revise scope/time explicitly |
| Which research question justifies the simulated preparation workflow? | Science + Automation | Yes before final demo | Generic handling fixture until reviewed evidence binding |

## Revision summary

The approved change broadens the architecture while keeping the hackathon focused on an evidence-backed patient-group journey. HPO and Reactome remain useful inputs, but neither they nor embeddings or clustering constrain future discovery channels.

This revision adds explicit DNA/transcript/RNA/assay representations, separates biological matching from asset reuse, preserves missing and contradictory evidence, supports synthetic individualized queries, and supplies implementation tasks and tests. It also adds the requested bounded robotics simulation with evidence-linked specifications, failure cases, and reproducible reports, while removing unsupported clinical routing, numerical confidence, treatment timelines, and the defective robot template.
