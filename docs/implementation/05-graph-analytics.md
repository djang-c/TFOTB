# 05 — Evidence Channels, Gates & Graph Queries

Implements: T06, T07, T08, T09 wiring, T18 (optional). The contract (`EvidenceChannel`,
`ChannelRegistry`, `ChannelComparison`) and gates (`ranking.py`) already exist. This doc specifies
the concrete channels and graph queries. **No combined weighted score** — PLAN removed the
0.45/0.35/0.20 formula; results are channel vectors + evidence categories.

## 1. `phenotype` channel (T06, P0)

- **IC** from a pinned, broad annotation corpus (HPO `phenotype.hpoa`, all annotated diseases — not
  the demo slice): `IC(t) = -log(p(t))`, where p counts diseases annotated with t or a descendant.
  Record HPO + annotation release versions in `score_definition`.
- **Comparison:** best-match-average of Lin similarity (Resnik MICA normalized), computed over
  terms *present* in both; avoid double-counting ancestors (use most specific annotated terms).
- **Polarity & missingness:** explicitly-absent terms are recorded separately; a term not mentioned
  is unknown, not absent. If a disease has no usable annotations → `availability: missing`.
- **Output explanation:** top shared high-IC terms in `context_matches`; low-IC terms (e.g.
  "Seizure") listed under `limitations` as "common, less informative".
- `score_definition`: `"BMA-Lin over HPO <ver>, IC from phenotype.hpoa <ver> (N diseases)"`.
- Temporal comparison (onset/progression) is P1.

## 2. `dna_variants` channel (T07, P0 curated)

- Exact normalized variant matches (assembly + transcript-versioned HGVS); related variants and
  documented functional effects from curated claims. **Same gene is reported separately from same
  variant** and never counts as mechanism support by itself.
- Mismatches recorded: inheritance incompatibility, assembly/transcript ambiguity (→ unresolved,
  not merged).

## 3. `rna_effects` channel (T07, P0 published/preprocessed findings only)

- Observed (`HAS_OBSERVED_RNA_EFFECT`) vs predicted (`HAS_PREDICTED_RNA_EFFECT`) kept distinct.
- Tissue/cell type mismatch → `context_mismatches: ["tissue"]` + caveat retained.
- No RNA findings → `availability: missing`, `score: null` (existing test).
- Numeric cross-study signature matching: disabled (PLAN).

## 4. `molecular_mechanisms` channel (T07, P0)

- Mechanism claims (`PERTURBS_MECHANISM`) with **effect direction**; Reactome/GO references as
  supporting identity, not as evidence by themselves.
- Opposite directions → `context_mismatches: ["effect_direction"]` → existing gate blocks
  shared-treatment inference while keeping the research connection visible.
- Plain-language mechanism labels come from a curated mapping table (cited).

## 5. `experimental_findings` channel (T08, P0 structured)

- Assay findings with model, assay, controls, intervention, units, positive/null/negative result,
  and `lineage_id`. Unlike assay contexts are not pooled numerically.

## 6. Gates & categories (T09) — existing code, wiring work

- `candidate_union` across channels → `compare_all` → `build_result` (exists).
- Add: coverage manifest per query; rank **within** categories with configurable tie-breakers
  (direct > indirect, reviewed > unreviewed, relevant context > mismatched); never across
  categories by a number.
- Independent-support counts use `independent_support_count` (lineage-aware, exists).

## 7. Graph projection & queries (`src/atlas/graph.py`)

NetworkX `MultiDiGraph` built from SQLite claims; every edge carries its `claim_id`.

- **Neighborhood for the optional canvas** (`max_nodes≈40`): always include the entity, its
  genes/mechanisms, top connections per category, related assets/orgs; phenotypes limited to
  shared high-IC terms, the rest collapsed into "+N more" with counts (`truncated`, `omitted`).
- **Paths** (for explanation): k-shortest simple paths (k=3, ≤4 hops) over claim edges, preferring
  reported + reviewed claims; a path whose only support is `inference` is returned as
  "hypothesis only", and if none exists → `GapResult(kind="no_supported_route")`. Each arrow of
  variant → transcript → RNA/protein → mechanism → phenotype is its own claim; missing arrows are
  shown, never filled.
- **Collaborators / network overlap** (brief Module 3.3): investigators with authored claims on two
  diseases served by different organizations; ranked with assets (practical), not biology. Each
  overlap shows the source claims on both sides, and matching is by full name + ORCID/affiliation
  with "name-based match" disclosed.
- **Asset ranking** (T10): access, contact validity, active status, applicability — separate list;
  never raises biological category.

## 8. Optional clustering (T18, P2)

Leiden only on a documented projection (declared edge eligibility + weights + version), presented
as an organization view; membership never implies shared treatment. First thing to cut.

## 9. Tests to add

- IC monotonic (child ≥ parent); BMA-Lin symmetric, in [0,1], self = 1.
- Explicitly-absent vs unknown phenotype handled differently.
- Same-gene-different-variant doesn't produce mechanism support.
- Path finder returns gap on the no-route fixture; never fabricates a missing arrow.
- Canvas neighborhood never exceeds `max_nodes`; omitted counts add up.
- Collaborator overlap requires ≥2 claims and shows both sides.
