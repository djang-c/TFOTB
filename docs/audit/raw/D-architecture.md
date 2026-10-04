# Audit D: architecture, performance, maintainability

Auditor: Agent D. Date: 2026-10-03. Repo HEAD: `c3abe9f`. Read-only audit; throwaway scripts in `/private/tmp/auditD/`. Machine: macOS (Darwin 24.6), Python 3.12 from `.venv`. All timings are single-run wall-clock on a developer laptop, not a deployment host; they are labelled as such.

Baseline: `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider` -> **373 passed, 0 skipped, 32.4 s**. `.venv/bin/ruff check .` -> **All checks passed**. mypy not run (not installed, per rules). Passing tests verify software behaviour, not scientific correctness.

## 1. Executive verdict

The scientific-logic skeleton is sound and mostly well tested at unit level: missing is kept as missing, no combined score exists, scores require a definition, hypotheses/predictions are mostly kept out of support, and assets are ranked separately from biology. But **the T09 engine that embodies those rules is only partly wired to the product**, and three of the headline plan promises do not hold against the code:

1. **Extensibility is not additive.** A new evidence channel with reviewed mechanistic support is categorised "hypothesis only" unless its ID is also hard-coded into `ranking.py:17` (`MECHANISM_CHANNELS`). The test that claims otherwise (`tests/test_channels.py:25`) only registers a channel that returns `missing`, so it cannot fail for this reason. (F1)
2. **The paper-extracted claim store (59 claims) never reaches ranking or the evidence brief.** The production registry holds only `phenotype` and `dna_variants` (the latter with `supports_category=False`), run over the 15,462 HPO-derived claims. Paper claims appear only in `/graph`, `/routes`, `/claims/{id}`. Real-disease `/connections` can therefore only ever output "symptom-level lead" or "hypothesis only"; the mechanism/literature categories and `conflicting_evidence` are unreachable on real data. (F2, F3)
3. **The end-goal input types mostly do not work.** Disease name, gene and single-symptom lookups work. Symptoms-only (multi-symptom -> candidate diseases), variant and research-question inputs have no implementation; the UI placeholder promises "mechanism" search which also does not exist. (Section 3)

Performance is fine for steady state (sub-millisecond to 50 ms cached) but the p95 < 2 s target is **not met for uncached paths**: the first `/entities/{disease}` request took 1.8-2.3 s (network call to ClinicalTrials.gov inside the request), and `/actions` takes ~0.75-1.1 s on **every** call. Deployment drops `data/store/` and `config/`, so the deployed API would not show the paper evidence at all.

## 2. Invariants table

Behaviour column = what I actually ran. "Real data" = pinned MONDO/HPO/HGNC via `SearchIndex.from_raw`. "Synthetic" = constructed in `/private/tmp/auditD/*.py` using `tests/conftest.py::make_claim`.

| # | Invariant | Code evidence | Verified behaviour | Result |
|---|---|---|---|---|
| I1 | Missing evidence never scored as dissimilarity | `schemas.py:243-248` validator forces `score=None` unless available; `channels/claims.py:86-91`, `phenotype.py:164-170` emit `missing`; `ranking.py:49-52` all-missing -> `insufficient_coverage`; `connections.py:_phenotype_similarity` returns 0.0 only as a sort position | Synthetic: phenotype `missing` candidate ranks last as `insufficient coverage`, no score. Real CLN3: `dna_variants` shows `missing` for NCL9, `available for 14 of 15` in coverage | PASS. Caveat: `connections.py` sort key uses 0.0 for missing, so a missing candidate ties with a genuinely 0.0-similarity one inside a category (cosmetic, same category rarely) |
| I2 | Missing never counts as confirmation | `ranking.py:57` mechanism channel counts only if it has support/contradiction | Synthetic: missing RNA + phenotype -> symptom-level lead (also `tests/test_ranking.py:11`) | PASS |
| I3 | Opposing effect direction handled | `channels/claims.py:110-113` sets `effect_direction`; `ranking.py:23,66` blocks shared-treatment | Unit test passes (`test_claim_channels.py:54`). **But** direction is a free string compared by set disjointness; synthetic "decreased" vs "down" -> `['effect_direction']` (false mismatch). `extraction.py:83` takes `direction: str | None` from the model with no normalisation. The real HPO claims carry no direction (context keys: `via, upstream, association_type`) | PARTIAL (works on normalised synthetic input; brittle on real LLM text; conservative error direction) (F6) |
| I4 | Opposing/contradicting claims reach `conflicting_evidence` | `ranking.py:53` keys on `contradicting_claim_ids`; **no production code sets it**: `grep contradicting_claim_ids src` -> only `ranking.py` reads it; `Claim.contradicts` is read only by demo-fixture routes (`routes.py:377`) | Real data: category never `conflicting evidence`. `ClaimOverlapChannel.compare` never fills `contradicting_claim_ids` | FAIL (dead path outside fixtures) (F3) |
| I5 | Transcript / genome-build context | `resolver.py:328-333` validates assembly + versioned transcript; `schemas.py:388` variant needs HGVS on versioned transcript | No channel compares assembly or transcript; `claims.py` mismatch set is only `effect_direction`, `tissue`, `assay`. `dna_variants` note: "gene-level only: no variant-level claims are modelled yet" (`channels/claims.py:143`). Variant claims cannot be produced at all | FAIL as a runtime gate; PASS as identity validation only (F4) |
| I6 | Tissue compatibility | `channels/claims.py:114-117` -> `tissue` mismatch; counts in `compatibility_flags` -> rank tie-breaker (`connections.py:_rank_key`) | Unit test passes. Tissue is free text ("brain" vs "cerebral cortex" -> false mismatch). It is a caveat, not a blocker (by design, `test_ranking.py:71`) | PARTIAL (same free-text brittleness) |
| I7 | Independent studies vs background restatements | `ranking.py:28-44` lineage-based counting with `scope == background` split; extraction defaults unsure -> background (`extraction.py:76`) | Works for repeated claims in one lineage (tests). **Counts each side's own paper:** synthetic Q-claim from paper p1 + C-claim from paper p2 sharing a GO term -> `literature-supported lead`, `independent_lineages = 2`, `direct = False`. Neither paper studies the Q-C connection. Also AI-hypothesis lineages (`STUDY:hyp-*`) are counted (`independent_support_count` has no source-type filter) | PARTIAL: the label "independent studies behind it" overstates (F5) |
| I8 | Hypotheses never change an evidence category | PLAN Revision 2026-10-04 item 4; `ranking.py:60-68` filters hypothesis predicates from `sup` only | Synthetic: phenotype alone -> `symptom-level lead`; phenotype + one AI `SHARES_PATHOGENIC_PATHWAY_WITH` hypothesis in `molecular_mechanisms` -> **`hypothesis only`** (demoted, because `mech` non-empty at `ranking.py:57` while `sup` is empty). Hypothesis lineage also counted as independent | FAIL against plan rule (conservative direction; not yet reachable in prod because of F2) (F7) |
| I9 | Predictions not support | `channels/claims.py:104` `observed_only` drops predicted RNA effects; `ranking.py:62` drops `SIMULATES_WORKFLOW_FOR` | Unit tests pass (`test_claim_channels.py:71`) | PASS |
| I10 | Same gene alone is not mechanism evidence | `supports_category=False` (`claims.py:23,100-103`) | Real CLN3: `dna_variants available`, `supporting_claim_ids=0` for all candidates; category stays symptom-level | PASS |
| I11 | Biological relevance separate from asset/collaborator relevance | Assets come from `trials.py` (condition-name match, ordered open-first); `schemas.py:530` "Ranked separately from biology"; `search.py:307` assets never enter `run_query`; collaborators endpoint is empty | Real CLN3/NPC: `/assets` ranking reasons are registry fields only; no category influence | PASS (collaborator side not implemented: `routes.py:282` returns `items=[]`) |
| I12 | Embeddings only retrieve, never prove | No embedding code exists (`grep -i embedding src robotics scripts` -> none relevant). T16 not built | n/a | PASS (vacuous) |
| I13 | Clustering optional, never evidence | No clustering code (only the owner's "seed cluster" constant `routes.py:149`) | n/a | PASS (vacuous) |
| I14 | No combined score | `connections.py` docstring + `_rank_key` is an ordered tuple; phenotype score only last tie-break; cards say "not a probability" | Real briefs: score printed with definition; no overall field in `ConnectionResult` | PASS. Note: ordering by phenotype similarity *within category* is a de facto ranking by one channel (owner-approved 2026-10-03) |
| I15 | Unknown channel renders without UI change | `frontend/src/components/Wells.tsx:23` falls back to `c.channel_id`; schema `channel_id: str` | Not run in a browser (UNVERIFIED visually). Wells colour an "available" well with the `ev-reviewed` token even when the data is a shared gene with no claim support (`Wells.tsx:39`) | PARTIAL (Low) |
| I16 | Extensible without rewriting schemas/UI/ranking | `channels/base.py` registry; see F1 | Synthetic: `proteomics` (reviewed mechanism claim) -> **hypothesis only**; same channel renamed `molecular_mechanisms` -> **reviewed mechanistic lead** | FAIL (F1) |

## 3. Input-type capability table

Run on real data (`SearchIndex.from_raw`, scripts `build.py`, `real.py`) and through `TestClient` (`api.py`).

| Input | Works today? | What it returns | What is missing |
|---|---|---|---|
| Disease name / synonym ("Batten disease", "Niemann-Pick type C", "CLN3") | Yes | Lexical hits with the matching label/synonym shown (`search.py:153`); entity page with: genes (HPO g2d claims), 12 phenotype neighbours with BMA-Lin similarity, ClinicalTrials.gov studies, GARD groups, template brief. Search "Batten disease" -> `MONDO:0019262` exact synonym | Mechanism/tissue/pathway not available from the pinned ontologies; paper evidence not in ranking (F2). Ambiguity flag is computed but "Batten disease" ranks a different MONDO than the seed CLN3 entry (design choice, resolver rule) |
| Gene ("NPC1", "CLN3") | Yes | Gene entity, diseases linked (HPO g2d), graph. `/connections`, `/gap`, `/actions` return empty for genes (`routes.py:249` only real *diseases*; 200 B payload) | No gene-level mechanism/tissue/variant view; no gene -> candidate disease hypotheses beyond HPO links |
| Variant (HGVS, rsID, "c.1054C>T") | **No** | `search("c.1054C>T")` -> `[]` (57 ms). `resolver.validate_variant_ref` exists but is not reachable from search or any route | No variant entity type in the index, no ClinVar/gnomAD source, no transcript/build gate on a query, no variant card (`cards.py:8` lists `variant_evidence` as "Not built") |
| Symptoms only, no disease named | **Partly: single term only** | One HPO term -> `/entities/HP:xxxx/related` = diseases annotated (incl. descendants), sorted by fewest annotations (`search.py:266`). Multi-symptom text ("ataxia and seizures and vision loss") -> `[]` after **2.6 s**. "ataxia seizures" returns diseases whose *names* contain those words ("Partington syndrome", "optic atrophy 10 ...") labelled "all words", which a user could misread as symptom-based candidates | No HPO phrase parser, no multi-term intersection/ranking endpoint, no candidate-hypothesis object with genes/phenotypes/mechanisms/tissues. The data are present: intersecting `ph._by_term` for Ataxia, Seizure, Visual loss gives **51 candidate diseases** in one set operation (`real.py`), so this is an unbuilt feature, not a data gap |
| Research question (free text) | **No (only retrieves papers, off by default)** | `search("what drugs treat CLN3")` -> `[]`. `POST /api/research` (`research_routes.py:78`) accepts a free-text `query`, but only discovers PubMed papers and stores claims; disabled unless `research_enabled`, needs `ANTHROPIC_API_KEY`; no answer synthesis endpoint (`/explain` returns fixture sentences keyed by entity id, `routes.py:385`) | No question parsing, no retrieval-to-answer path, no grounded answer. UI placeholder "disease, gene, symptom or mechanism" (`frontend/src/components/SearchBox.tsx:8`) over-promises "mechanism" (no mechanism entity type in `ENTITY_TYPES`) |

## 4. Performance

Commands (all from repo root):

```
PYTHONPATH=src .venv/bin/python /private/tmp/auditD/build.py    # index build, memory, search latency
PYTHONPATH=src .venv/bin/python /private/tmp/auditD/api.py      # FastAPI TestClient, per-endpoint, 5 calls each
PYTHONPATH=src .venv/bin/python /private/tmp/auditD/prof.py     # cProfile of actions(), find_paths, build_graph
PYTHONPATH=src .venv/bin/python /private/tmp/auditD/scale.py   # synthetic 1k/5k/15k claims
PYTHONPATH=src .venv/bin/python /private/tmp/auditD/trials.py   # failure caching
```

### Startup and memory

| Measurement | Value |
|---|---|
| `import atlas.search` | 0.19 s |
| `SearchIndex.from_raw` (MONDO+HGNC+HPO, 361,810 names, 15,462 HPO claims) | **10.3 s** (PLAN/lifespan comment says ~5 s) |
| Peak RSS after build | **1,253 MB**; after API session 1,273 MB |
| `create_app()` | 0.26 s |
| `/api/health` before index ready | 7 ms, returns `ok` while the first `/search` blocked **10.3 s** on `_index_lock` (`routes.py:36-42`) |
| Raw-file SHA-256 verification (7 files, 459 MB) | all match `CHECKSUMS.json`; takes under 0.5 s total; **not performed at runtime**, only at deploy build |

### Per-endpoint latency, real entities (TestClient, in-process; ms)

| Endpoint | First call | Steady (p50 of calls 2-5) | Note |
|---|---|---|---|
| `/entities/MONDO:0008767` (CLN3 disease) | **2,343** | 0.9 | first call runs `connections` (134 ms cold) + live ClinicalTrials.gov fetch (~0.6-0.8 s measured in profile) + GARD fetch |
| `/entities/MONDO:0018982` (NPC) | **1,822** | 1.4 | same |
| `/entities/{id}/related` (CLN3 / NPC) | 48 / 161 | 47.6 / 161.2 | **not cached**, recomputed each call |
| `/entities/{id}/connections` | 1.1 (after `/entities`) | 0.8 | cold cost is 134 ms (CLN3), 233 ms (NPC), 143 ms (NPC1-disease) in `prof.py` |
| `/entities/{id}/assets`, `/groups` | 0.6 | 0.5 | cached 24 h in process (see F9) |
| `/entities/{id}/graph` | 2.7 | 1.2 | 20 KB payload |
| `/entities/{id}/actions` | **752** | **891** (max 1,040) | **recomputed every call** (F8) |
| `/api/meta` | 216 | not re-measured | 4 seed `related()` calls each time |
| gene / phenotype endpoints | 0.4-2 | 0.4-1.6 | trivial |

`cProfile` of `ix.actions("MONDO:0008767")` = 1.90 s: `evidence_brief` 1.12 s (10 x `find_paths` at 0.108 s each, 0.643 s of it in `_simple`), `assets` 0.78 s (0.77 s in `_http_get`, a live network call).

PLAN target p95 < 2 s for cached graph results: **met for cached routes; not met for first-touch `/entities/{disease}` (1.8-2.3 s) and borderline-to-near for `/actions` (0.75-1.1 s, never cached).**

### Scaling on synthetic claims (random graph, 300 diseases, ~400 features)

| Claims | `run_query` (4 claim channels) | candidates | `build_graph` | `neighborhood` (40 / 200 nodes) | `find_paths` |
|---|---|---|---|---|---|
| 1,000 | 2 ms | 1 | 2 ms | 2 / 2 ms | 14 ms |
| 5,000 | 60 ms | 18 | 6 ms | 10 / 12 ms | 20 ms (no-path 23 ms) |
| 15,000 | **1,705 ms** | 155 | 37 ms | 45 / 76 ms | 38 ms (no-path 26 ms) |

`run_query` is roughly O(candidates x claims x channels): `ClaimOverlapChannel._claims()` re-scans every claim per call (`channels/claims.py:44`), and `compare` calls it again for `direct` (`:84`) plus `_features` twice. Today this is hidden because only `dna_variants` runs over the HPO store (134-233 ms). Registering the other three claim channels (the plan's design) would put real queries near the 2 s limit at 15k claims. `find_paths` and `neighborhood` are not the bottleneck at these sizes; `shortest_simple_paths` is capped at 50 paths (`graph.py:96`). A worst-case dense/lattice graph was not tested: UNVERIFIED.

SQLite: `AtlasDB.put` x 5,000 = 1.98 s (one transaction per row, `db.py:put`); `load_claims` 5,000 = 29 ms cold, 0 ms cached (mtime-keyed `lru_cache`, `api/claimstore.py:17`). The read path is fine; the write path is only used by offline ingest.

### Reproducibility and deployment

- `requirements.lock`: 43 exact `==` pins, no `--hash`. `anthropic` and `pypdf` are installed in `.venv` (anthropic 1.11.0, pypdf 6.19.0) but **not in the lock** (`docs/DECISIONS.md` line 44 admits pypdf is "not in requirements.lock"; `pyproject.toml:11` says anthropic is "not installed/pinned yet"). The ingest that produced `data/store/atlas.db` therefore cannot be reproduced from the lock.
- `data/raw/CHECKSUMS.json` verified by me (all 7 OK). Dockerfile fetch (`scripts/fetch_for_deploy.py`) fails the build on mismatch, but HGNC/GO/ChEBI/MONDO URLs are unversioned ("current"), so a future upstream release breaks the build rather than the data (fail-closed, but not reproducible over time).
- Run manifests: `data/manifests/` holds three markdown audits; no per-run manifest with code commit + env lock + data hash + seed for the ingest runs (`data/store/ingest_log.jsonl` records model/prompt/citation but no commit, lock hash or seed). The LLM cache that would allow replay (`data/cache/llm`) and the store (`data/store/`) are both gitignored (`.gitignore` lines for `data/cache/`, `data/store/`), so **a fresh clone has zero paper claims and cannot replay them**.
- Deploy image (`deploy/api.Dockerfile`, `.github/workflows/deploy-api.yml`): copies `src/`, `data/fixtures/`, `CHECKSUMS.json`, fetch script, lock. It does **not** copy `data/store/` (so no paper claims served), `config/ingest_policy.json` (`load_policy` silently falls back to defaults, `policy.py:load_policy`, hence `hide_drug_claims` and caps differ from local), or `data/aliases.json` (public search deliberately ignores aliases, so no effect). Workflow trigger paths omit `config/**`. No workflow runs tests or ruff before pushing to the Space (`.github/workflows/` contains only `deploy-api.yml`).
- Runtime network calls in the request path: ClinicalTrials.gov (`trials.py:_http_get`, 8 s timeout) and GARD (`gard.py:103`, 10 s timeout). On a failure the failed result is cached for 24 h (F9). Results change over time, so the same request is not reproducible; no disk cache.
- Readiness: `/health` returns ok before the 10 s index build finishes; the first user search then stalls on the lock (measured 10.3 s locally; a 2-vCPU free Space is likely slower, UNVERIFIED).

## 5. Findings

Severity: Critical = breaks a plan invariant or the demo on the default path; High = plan promise unmet or user-visible wrong behaviour; Medium = correctness/perf risk; Low = hygiene.

### F1 (High). New channels are not addable without editing `ranking.py`
- `src/atlas/ranking.py:17` hard-codes `MECHANISM_CHANNELS`; `categorize` (`:49-76`) treats any other channel ID as non-evidence (only `phenotype` is special-cased at `:59`).
- Repro: `/private/tmp/auditD/ext.py`. A `proteomics` channel returning `available` + one reviewed `PERTURBS_MECHANISM` claim -> `hypothesis only`. Renamed to `molecular_mechanisms` -> `reviewed mechanistic lead`.
- The "extensibility" test (`tests/test_channels.py:25-37`) registers a channel that always returns `missing` and asserts `insufficient coverage`; it would pass even if registration did nothing useful. Tautological for the plan's claim (PLAN Goals: "Add a new evidence-channel implementation without rewriting the graph schema, result contract, or UI").
- Fix: put `kind: Literal["mechanism","phenotype","context"]` (or `contributes_to_category: bool`) on `EvidenceChannel` and have `categorize` read it from the comparison/registry; add a test that registers an available mechanism channel under a new ID and asserts the category.

### F2 (High). Paper-extracted claims never enter ranking, gaps or the evidence brief
- `src/atlas/search.py:121-126` registers `phenotype` and only `dna_variants`; `:292` runs `run_query` over `self.store.claims`, which is built only from HPO g2d (`:100-103`). `api/routes.py:87-90` loads the paper store but uses it only in `/graph`, `/routes`, `/claims/{id}`.
- Evidence: `real.py`: `PMID` appears in neither CLN3 connection support nor in `ix.actions(...)[0]["body_markdown"]`. `data/store/atlas.db` holds 59 claims (41 `GENE_ASSOCIATED_WITH_DISEASE`, 9 `ACCUMULATES_IN_COMPARTMENT`, 6 `CANDIDATE_THERAPY_FOR`, 2 `SHARES_PATHOGENIC_PATHWAY_WITH`, 1 `AFFECTS_TRANSCRIPT`); none can influence a category. The frontend text "Evidence from papers is not extracted yet" (`frontend/src/app/page.tsx:204`) is consistent with this but contradicts `/graph` showing them.
- Fix: build the registry from the union of HPO claims and `load_claims(...)`, register all four `build_claim_channels`, cache the outcome per store mtime.

### F3 (High). `conflicting_evidence` is unreachable outside fixtures
- `ranking.py:53` and `connections.py:_gap` consume `contradicting_claim_ids`, but no channel sets it (`grep -rn contradicting_claim_ids src` -> readers only). `Claim.contradicts` is unused by channels.
- Plan fixture requirements ("a contradictory finding") are therefore met only by demo JSON. Opposing direction is surfaced as a context mismatch but never as a contradiction category.
- Fix: in `ClaimOverlapChannel.compare`, when direction disjoint, put the opposing claim IDs in `contradicting_claim_ids`; also honour `Claim.contradicts`. Add a test through `run_query`, not `categorize` alone.

### F4 (High). No variant/transcript/build handling at runtime
- Identity validation exists (`resolver.py:328-333`, `schemas.py:388`) but no channel, route or search path uses it; `channels/claims.py:143` states gene-level only. The PLAN's "transcript/genome-build context" invariant is therefore not enforced where it matters (comparison). No variant search (Section 3).
- Fix (minimum): add `assembly` and `transcript` to the mismatch set in `ClaimOverlapChannel` and a `/entities/variant:...` resolver route; otherwise state plainly in the UI that variants are unsupported.

### F5 (Medium). "Independent studies" counts per-side papers and hypothesis lineages
- `connections.py:156` passes `res.path_claim_ids` (claims from both diseases) to `independent_support_count` (`ranking.py:28`). Repro `indep.py`: two papers, each about one disease sharing a GO term -> `literature-supported lead`, `independent_lineages=2`, `direct=False`. Also no source-type filter, so `STUDY:hyp-*` lineages count (`hypotheses.py:170`).
- Fix: count independent lineages only over claims that bridge the pair (direct claims, or per-feature pairs with a lineage on each side reported separately as "side A: n, side B: m"), and exclude `ai_generated`/inference claims.

### F6 (Medium). Free-text direction/tissue/assay compared by string equality
- `channels/claims.py:110-120`; `extraction.py:83` (`direction: str | None`). Repro `indep.py`: "decreased" vs "down" -> `effect_direction`. Errors are in the conservative direction (they block a shared-treatment inference) but will produce noisy "opposing mechanism" flags on real LLM output.
- Fix: normalise direction to an enum (`up|down|none`) at extraction, quarantine otherwise; use ontology IDs (UBERON) for tissue or mark tissue mismatch "unverified text".

### F7 (Medium). AI hypotheses can change the category and count as independent
- `ranking.py:57-68`. Repro `hyp.py`: phenotype alone -> `symptom-level lead`; with one AI hypothesis in `molecular_mechanisms` -> `hypothesis only`. PLAN Revision 2026-10-04 item 4: hypotheses "never change an evidence category".
- Fix: drop hypothesis-only predicates / `ai_generated` claims from `supporting_claim_ids` before the `mech` filter, and from lineage counts.

### F8 (Medium). `/actions` and `/related` are recomputed per request; per-candidate graph rebuild
- `cards.py:145` `find_paths(claims, a, b)` is called once per shown candidate (up to 10), and each call rebuilds `build_graph` + `_simple` of the whole claim set (`graph.py:90-91`); 0.108 s each at 15k claims, 1.1 s of the 1.9 s `actions()` profile. `search.py:475` caches nothing (`_outcomes` caches only the connection outcome). `/related` costs 48-161 ms each time.
- Fix: build the graph once per claim-store version and pass it into `find_paths`/`neighborhood`; cache `actions()` by `(entity_id, manifest_id)`. Expected effect: `/actions` 0.9 s -> tens of ms (not measured after change).

### F9 (Medium). Live network in the request path; failures cached for 24 h
- `trials.py:59` caches the result of `_build` including the failed-source dict (`:70`); repro `trials.py`: first call fails, second returns `failed` without refetching (1 fetch call). Same pattern at `gard.py:63`. A 1-second outage on first touch hides assets/groups for 24 h; in-memory only, lost on restart, not thread-safe. First-touch `/entities/{disease}` cost 1.8-2.3 s is dominated by this network call.
- Fix: do not cache failures (or cache them for ~60 s), prefetch the seed diseases at startup or ship a dated snapshot with provenance (`retrieved_at`), and set a short timeout.

### F10 (Medium). Deployed API does not match local behaviour
- `deploy/api.Dockerfile` copies neither `data/store/` nor `config/`; `.github/workflows/deploy-api.yml` `paths:` omits `config/**`; no tests/ruff in CI; no store snapshot is tracked (`.gitignore`: `data/store/`, `data/cache/`). The live demo would show no paper claims, and `/api/research` would be off (default) regardless. `docs/DEPLOY.md` "What ships" does not mention the store.
- Fix: ship a verified snapshot (the `db.export_snapshot` format already exists, `db.py`) into the image and load it; add a CI job running pytest + ruff before deploy; version-pin the data URLs.

### F11 (Medium). Index build 10.3 s, 1.25 GB RSS, and `/health` is not a readiness check
- `api/app.py:22-26` starts a thread; `/health` (`routes.py:121`) returns ok immediately. First search blocks on `_index_lock`. On a free CPU Space the HF health check will pass and users will hit a 10+ s hang.
- Fix: add `/ready` that reports index state; or build lazily with a loading response (HTTP 503 + `Retry-After`).

### F12 (Medium). Stubs still serve the product surface
- `routes.py:1-4` docstring says "Stub routes ... SYNTHETIC demo" (stale); `/collaborators` always `items=[]` (`:282`); `POST /explain` and `POST /actions` return demo fixtures for any entity (`:385-393`); `POST /uploads` returns a fixture (`:396`). The plan's collaborator and upload/quarantine journey (T10/T11) is not served. These are labelled `_synthetic` but are dead weight in a "real" API.

### F13 (Low). Maintainability
- Duplicates: `REVIEWER_ROLE` in `connections.py:39` and `graph.py:28`; `_curie`/`_PURL` in `search.py:517` and `channels/phenotype.py:23-29`; MONDO `is_a` parsing in `search.py:from_raw` and `phenotype.py:from_raw`.
- `search.py` (529 lines) is a god object: ontology matching, SQLite FTS, g2d claim building, trials/GARD adapters, T09 orchestration, template summaries and card assembly.
- Ownership: `api/routes.py` has 3 authors (12 ANonABento, 3 Kevin Jiang, 2 djang-c commits), `schemas.py` 3 authors, `cards.py` and `connections.py` single-author; the Builder A/B split in the brief is not visible in git ownership of `schemas.py`/`routes.py`. Only commit authorship was inspected; I did not find a written ownership list: UNVERIFIED which files were assigned to whom.
- `.gitignore` ignores `data/store.*/` but `data/store.before-provenance/*` is tracked (force-added), including `atlas.db`. Low, but a binary DB with unreviewed claims is in git history.
- Real-data tests skip silently when `data/raw` is absent (`tests/test_search.py:79`, `test_resolver.py:129,215,239`, `test_phenotype_channel.py:99`); with no CI that runs them, the real-ontology path is only tested on machines that downloaded the files. `data/raw` checksums are not verified by any test or at runtime.
- Tests that cannot fail for their stated purpose: `tests/test_channels.py:25` (F1). Most other unit tests assert specific values; I did not audit all 294 test functions: UNVERIFIED beyond a grep for `assert True` (none) and `is not None`-only asserts (three, each a gap check with an additional condition elsewhere).
- Coverage gaps for plan rules: no test for category behaviour through `run_query` with a new channel ID (F1); no test that paper-store claims influence ranking (F2); none that asserts `contradicting_claim_ids` is populated by a channel (F3); none for hypotheses vs category (F7); no deployment parity test.

## 6. What passes (so the above is not read as blanket failure)
- Schema-enforced missingness (`ChannelComparison` validator), scoped gaps instead of guesses (`connections.py:_gap`, `graph.py:find_paths`), `observed_only` and `supports_category` flags, "same compartment, different substance is not a shared feature", no combined score anywhere, simulation records excluded from biology, labelled provenance on every payload, read-only store connection (`claimstore.py:19`), claim immutability by PK (`db.py:put`), snapshot checksum verification (`db.py:load_snapshot`).

## 7. Unverified list
- Latency on the actual Hugging Face Space (2 vCPU, cold container); all numbers are laptop, in-process TestClient (no network/serialization of a real server, no concurrency).
- Behaviour under concurrent requests (first-request lock contention beyond the single measurement; `TrialsSource`/`GardSource` cache thread safety).
- Pathological `find_paths` cases (dense lattice, hubs); only a random graph to 15k claims was tested.
- Frontend rendering of an unknown channel ID and the green "available" well for a shared-gene-only channel (read the code, did not run a browser).
- Whether the Docker image builds and starts (not built; Docker not used; no network use beyond the profile run that already touched ClinicalTrials.gov through the app's own code path).
- ClinicalTrials.gov/GARD content correctness; assets' scientific relevance.
- Full coverage metric (coverage tool not installed) and the remainder of the 294 test functions.
- Whether the owner intends Builder A/B file assignments beyond what git authorship shows.
