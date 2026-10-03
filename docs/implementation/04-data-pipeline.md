# 04 — Data Pipeline (Reproducible Seed Slice)

Implements: T01 (tooling side), T03, T04. **Every connector is gated on a completed row in
`data/manifests/source_manifest.md`** (access, licence/terms, fields, rate limits, version) — PLAN
requires verifying this before use.

Goal: `make data` rebuilds `data/build/atlas.db` + a versioned JSON snapshot deterministically from cached raw pulls +
a small curated overlay. `make data-refresh` re-pulls from the public APIs. The README documents
both — this satisfies "README covering … how to reproduce the dataset".

## 1. Sources

| Source | Access | Used for | `source_type` |
|---|---|---|---|
| MONDO (`mondo.json`/`.obo`, OBO Foundry PURL) | bulk file | Disease IDs, labels, synonyms, xrefs (OMIM/Orphanet), definitions | database_record |
| HPO (`hp.obo`, `phenotype.hpoa`, `genes_to_disease.txt`) | bulk files (HPO GitHub releases) | Disease→phenotype w/ frequency; IC computed over **all** annotated diseases; gene→disease | database_record |
| HGNC | REST (`rest.genenames.org`) | Gene symbols, IDs, aliases | database_record |
| ClinVar | NCBI E-utilities (`esearch`/`esummary`) | Variants for cluster genes; source-reported classification + review status kept verbatim | database_record |
| Reactome | ContentService / `UniProt2Reactome` mapping | Gene→pathway (lowest-level pathways) | database_record |
| GO (optional) | GAF via QuickGO | Cellular component (lysosomal membrane etc.) | database_record |
| PubMed | E-utilities `esearch`/`efetch` (abstracts, authors, affiliations) | Publications, quotes, investigators | published (preprints flagged in context) |
| ClinicalTrials.gov | API v2 `/api/v2/studies` | Interventional + observational/natural-history studies, sites, eligibility | database_record |
| NIH RePORTER | API v2 `/v2/projects/search` | Funded projects, PIs (network overlap, funders) | database_record |
| Orphanet / Orphadata | bulk XML/JSON | Prevalence class, gene associations, cross-check | database_record |
| ChEMBL / openFDA labels | REST | Drug targets, approval status | database_record |
| Patient orgs & registries | **curated YAML** with URL + `verified_at` | Communities and assets | database_record |

OMIM bulk files require a license — we use OMIM IDs only as xrefs via MONDO, not OMIM content.

## 2. Pipeline steps (`scripts/pipeline/`)

Each step: reads previous outputs, writes to `data/interim/NN_*.json`, is idempotent, logs counts.

| # | Script | Output | Notes |
|---|---|---|---|
| 01 | `fetch_ontologies.py` | MONDO/HPO files in `data/raw/` w/ checksums | Version + date recorded in manifest |
| 02 | `select_cluster.py` | disease set | Input: `data/curated/seed_diseases.yaml` (MONDO IDs + reason). Expands via MONDO subclass + gene neighbours, capped |
| 03 | `fetch_genes.py` | gene nodes, gene→disease edges | HPO `genes_to_disease` + HGNC |
| 04 | `fetch_variants.py` | variant nodes | ClinVar P/LP per gene (cap ~10 each) + demo variants |
| 05 | `fetch_pathways.py` | mechanism nodes, gene→mechanism edges | Reactome lowest-level; map to plain labels via curated table |
| 06 | `fetch_literature.py` | publication nodes, investigator candidates | Per disease: key reviews + ≤10 top-relevance papers; store abstracts |
| 07 | `fetch_studies.py` | study nodes, study edges | CT.gov by condition synonyms; RePORTER by gene/disease terms |
| 08 | `extract_claims.py` | candidate `Claim`s from permitted passages | **LLM bounded extraction** (doc 06), recorded to `llm_cache/`; quote verification; ID resolution via T03 resolver; failures → quarantine |
| 09 | `merge_curated.py` | org/asset/counterexample nodes+edges | From `data/curated/*.yaml`; every entry requires `source_url` |
| 10 | `precompute_channels.py` | IC table + cached `ChannelComparison`s per disease pair | Doc 05; no combined score |
| 11 | `derive_collaborators.py` | investigator ↔ disease links (from authorship) | Name disambiguation rules below; ranked with assets, never as biology |
| 12 | `generate_explanations.py` | cached per-claim plain sentences + entity summaries | Grounded explanation (doc 06), cached + labelled |
| 13 | `validate.py` | `data/build/validation_report.md` | Fails build on invariant violations |
| 14 | `export.py` | SQLite `atlas.db` + versioned JSON snapshot + `meta.json` | |

## 3. Curated overlay format

```yaml
# data/curated/patient_orgs.yaml
- id: FOTB:org/<slug>
  label: <Organization name>
  serves: [MONDO:xxxxxxx]           # verified MONDO IDs only
  website: https://...
  contact_url: https://...           # org-level contact page, not personal emails
  source_url: https://...            # page that states it serves this disease
  verified_at: 2026-10-xx
  verified_by: <teammate initials>

# data/curated/assets.yaml  (registries, natural-history studies, models, biomarkers)
- id: FOTB:asset/<slug>
  asset_kind: REGISTRY
  label: ...
  covers: [MONDO:...]
  maintained_by: FOTB:org/<slug>
  data_fields: [age_at_onset, seizure_frequency, vision_score, motor_score, ...]
  access: on_request
  source_url: https://...
  linked_studies: [NCT........]
  verified_at: 2026-10-xx

# data/curated/counterexamples.yaml
- disease_a: MONDO:...
  disease_b: MONDO:...
  note: "High phenotype overlap, different primary mechanism"
  source_ids: [PMID:...]
```

## 4. Integrity rules (enforced in `validate.py`)

- Every CURIE must appear in a raw source file or API response we stored. No hand-typed IDs.
- Quote verification: `quote_verified = normalize(quote) in normalize(abstract_or_page_text)`.
  Report the verification rate; target ≥95% for displayed quotes. Unverified → shown as paraphrase.
- No orphan nodes in the build (except search-only synonyms).
- Every claim has a `lineage_id`; repeated reports of one experiment share it.
- Coverage counts in manifests are written by the fetch steps (recorded operations), never by an LLM.
- Reviewed claims (`review_state=reviewed`) require a reviewer entry in `data/curated/reviews.yaml`.
- Investigator nodes: created only for authors with ≥2 publications in the cluster, matched by
  full name + (ORCID if present, else normalized affiliation). Overlap claims across diseases show
  "matched by name + affiliation" and the papers, so a human can check.
- Synthetic demo variants/cases live in `data/curated/synthetic_cases.yaml` (`CASE-SYN-*`,
  `source_type: synthetic_fixture`) and go only to the isolated `CaseStore`, never the public store.

## 5. Budgets & etiquette

- NCBI: ≤3 req/s without key, ≤10 with `NCBI_API_KEY`; set `tool` + `email` params.
- Cache every raw response to `data/raw/<source>/<hash>.json`; refresh only on `make data-refresh`.
- LLM extraction budget: 20–40 passages (PLAN target) — trivial; record everything.

## 6. How it scales (README section, not built)

Same pipeline, seed list = all MONDO rare diseases with HPO annotations; swap NetworkX for Neo4j or
a graph DB; batch extraction; community-submitted overlays reviewed via PR. The demo shows the
*mechanism*, the README shows the path.
