# 12 — Breadth Layer: every disease, with a verified depth slice

Status: added 2026-10-03 at the project owner's direction. **PLAN.md stays authoritative.** PLAN's
"6–10 diseases / 10–20 curated findings" (line 385) are *seed workload targets for the hand-verified
fixture*, and PLAN line 504 requires the architecture to stay extensible. This doc adds the breadth
the product is actually for, without relaxing any provenance rule.

## 1. Two layers

| | Breadth layer | Depth layer (T01 slice) |
|---|---|---|
| Scope | All diseases covered by the public bulk sources (MONDO, HPO annotations, Orphanet, HGNC, Reactome, ClinVar, PubMed/CT.gov by query) | The audited cluster: 6–10 diseases, hand-verified claims |
| How built | Automated, deterministic pipeline (doc 04) with `--scope all` | Curated + reviewed (T01), `reviewed` only after a named human reviews it |
| Output label | `computational_prediction` / `inference` candidates; evidence category capped at **hypothesis only** unless supporting reviewed claims exist | Can reach "reviewed mechanistic lead" |
| Purpose | Find connections no one searched for; ranked candidates for expert review | Proves the pipeline is traceable; acts as the **evaluation set** for the breadth layer |

Demo framing: "searched every rare disease → drill into the verified slice". Never present a
breadth-layer candidate as a finding.

## 2. What runs over everything (no per-disease curation)

- **Phenotype channel** (doc 05 §1) — IC is already computed over all annotated diseases.
- **Gene / pathway sharing** — HPO `genes_to_disease` + Reactome; same gene reported separately
  from same mechanism (existing rule).
- **Literature retrieval** (T16) — embeddings retrieve candidate papers/entities; embedding-only
  hits stay `hypothesis` (PLAN line 109/412).
- **Graph model channel (new, P1, T26)** — a graph neural network (link prediction) over the
  public knowledge graph built by the pipeline. It is an ordinary `EvidenceChannel`: it returns a
  `ChannelComparison` with `observation_kind=computational_prediction`, a `score_definition`
  naming model, version, training data and split, and **never** a calibrated probability or
  "confidence". Like simulation, a model score can rank candidates for review but can never be the
  support that promotes a category (same gate as `ranking.py` "sim-never-support").
- **LLMs** (doc 06) — extraction, reconciliation suggestions and grounded explanation; the model
  proposes, code disposes.

## 3. Rules that do not relax at scale

1. Predictions are labelled `PREDICTION`/`HYPOTHESIS` until an experiment tests them (charter §2).
2. Every displayed claim keeps provenance (source, span, lineage). Bulk loads record source
   version + retrieval date + checksum; licence terms are in the manifest before use (T01).
3. Missing ≠ zero: a disease absent from a source is `availability: missing`, not a low score.
4. Public data only goes to any external service (Anthropic, OpenAI, Databricks, …); each new
   outbound use needs explicit human approval (charter §8). No PHI/PII.
5. Models are evaluated before any performance claim: held-out known edges **with leakage control**
   (split by time or by hiding edges, no shared test/train identifiers), baselines (e.g. phenotype
   similarity alone, popularity), N and CIs reported, results labelled exploratory unless run
   against a locked analysis plan. Without this, the README says "no accuracy claim".
6. Images / ViTs: not planned until a specific, licensed, non-identifiable imaging dataset is
   named. No imaging model ships on the strength of the architecture alone.
7. A Databricks endpoint (LLM or compute) would sit behind `LLMClient` / the pipeline as another
   adapter; which Databricks APIs are available is an open question (doc 11).

## 4. New tasks (appended to PLAN's T-list; not PLAN items)

| ID | Task | Priority | Depends on | Output |
|---|---|---|---|---|
| T25 | Broad ingestion: pipeline steps 01–05 and 10 with `--scope all` over the bulk sources | P0 for breadth | T01 manifest rows for each source, T02, T03 | `atlas.db` with all-disease nodes/edges, phenotype IC + cached channel comparisons, versioned snapshot |
| T26 | Graph-model channel (link prediction) + evaluation harness | P1 / cut first | T25 | Channel registered behind the contract; eval report with leakage-controlled split, baselines, N, CI; or an explicit "no accuracy claim" |
| T27 | Breadth UX: dataset badge ("N diseases, source versions"), candidate vs reviewed styling | P0 | T25, T12 | UI never shows a breadth candidate as reviewed |

T26 is the first thing to cut if T25 slips; T25 and T27 are not cut (they are the product).
