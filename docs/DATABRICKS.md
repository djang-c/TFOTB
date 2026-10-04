# Databricks storage and weekly refresh: DESIGN NOTE (nothing here is built)

Status 2026-10-03. This is a proposal for owner and Builder B (Keving) review. No Databricks workspace has been inspected: which features the account includes (Jobs, Unity Catalog, serving) is UNVERIFIED. The $100 credit is reserved for deployment (DECISIONS.md), so a weekly job must fit inside what is left, or wait.

## Principles carried over from PLAN
- Raw files are immutable and hashed; processed tables are rebuilt from raw by a script.
- Everything extracted is `unreviewed`. Automation never promotes a claim.
- Missing stays missing. No combined score, no LLM confidence.
- No dataset in the public GitHub repo. No outward upload without owner approval.
- Counts in coverage manifests come from recorded runs.

## Layers (Delta tables, one schema `tfotb`)
| Layer | Table | Rows are | Built from | Notes |
|---|---|---|---|---|
| raw | `raw_files` | one per downloaded file | `fetch_ontologies.py` | name, url, sha256, bytes, retrieved. Files themselves in a volume, read-only. |
| raw | `raw_papers` | one per fetched paper | PubMed / Europe PMC APIs | source_id, url, licence, retrieved, text_hash. Full text NOT mirrored unless the licence allows; keep the hash and a pointer. |
| reference | `entities` | disease / gene / phenotype | MONDO, HGNC, HPO | id, type, label, synonyms (tier), release version |
| reference | `phenotype_graph` | is_a edges | HPO | child, parent |
| reference | `disease_phenotype` | annotations | phenotype.hpoa mapped to MONDO | disease, hpo_id, negated flag; unmapped sources listed in `unmapped_sources` |
| claims | `claims` | one per verified statement | extraction | claim_id, subject_id, predicate, object_id, quote, source_id, lineage, status, review_state, context (JSON), prompt_version |
| claims | `quarantine` | one per rejected statement | extraction | source_id, raw statement, reason |
| claims | `extraction_runs` | one per paper per run | extraction | provider, model, prompt_version, from_cache, claims_added, quarantined, status |
| output | `query_results` | ranked connections | `run_query` | query, candidate, category, path_claim_ids, comparisons (JSON), manifest_id |
| output | `coverage_manifests`, `gaps` | one per query | `run_query` | deterministic `COV:` ID |
| ops | `refresh_runs` | one per weekly run | job | start/end, counts, failures, spend |

Delta table versions give "as of" snapshots, which is what the coverage manifest's `dataset_version` should point at.

## Weekly refresh job (proposed)
1. **Fetch ontologies**: only if the pinned release changed; hash-verify; never overwrite.
2. **Find new papers** for the cluster's search terms via official APIs (PubMed E-utilities needs `NCBI_API_KEY` + `NCBI_EMAIL`; Europe PMC for open-access full text). No HTML scraping.
3. **Skip** papers whose `source_id` is already in `extraction_runs` with the same `prompt_version`.
4. **Extract** the new ones, with a hard per-run cap on papers and tokens. Stop and report when the cap is hit; do not continue silently.
5. **Ingest**: verified claims to `claims` as `unreviewed`, rejects to `quarantine`, one row per paper to `extraction_runs`.
6. **Recompute** query outputs for the cluster and write `coverage_manifests`.
7. **Write `refresh_runs`** with real counts and any failed source. A failed source is reported, never hidden.

## Decisions needed from the owner
- Spend cap per weekly run, and whether it comes out of the reserved deployment credit.
- Which search terms define "the cluster" for fetching (CLN3 / NPC only, or wider).
- Licence stance on storing full text vs hash+quote only (HPO commercial terms also still open).
- Who reviews the growing unreviewed pile. With no expert assigned, the weekly job only grows the unreviewed set.

## Not verified
- The OpenAI adapter runs live from a workstation; it has not been run from Databricks.
- Real extraction quality is unknown: we have seen zero real papers go through it.
- Databricks plan features and per-run cost are unknown.

## Built locally on 2026-10-03 (still no Databricks code)
`src/atlas/pipeline.py` + `scripts/ingest_papers.py` are the single-machine form of weekly steps 3-5 (fetch, extract, store). They write the existing SQLite store (`data/store/atlas.db`, git-ignored) and a checksummed snapshot, and keep an append-only run log. Guards: the licence of each paper is recorded in the run log (any open-access paper is accepted; owner decision, hackathon project), a per-run paper cap, a size cap, replay-only by default (a paid call needs `--live` + `--i-approve-sending-these-texts` + the key). Not built: paper DISCOVERY (needs the owner's search terms), the Databricks wrapper, Delta tables, the schedule, any spend cap. A Databricks job would call `ingest_papers` unchanged.

## Update 2026-10-03: unattended by policy
Per the owner ("the point is to automate; per-run approval defeats it"), the per-run approval flags are gone. `config/ingest_policy.json` is the standing policy: live calls on/off, caps on papers per run and text size, and the diseases to watch. `src/atlas/discovery.py` finds new open-access papers from the watched diseases' own ontology names (title or abstract match, newest first), so nobody supplies keywords. A Databricks job would run `scripts/ingest_papers.py` on a schedule with the same policy file. Still the owner's call: the numbers in the policy (the cap is a placeholder of 5 papers per run) and the weekly schedule.
