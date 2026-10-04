# 06 — AI Layer (OpenAI): Extract · Reconcile · Explain

Implements: T04 (bounded extraction), reconciliation *suggestions* for T03, grounded explanation
for T12, action prose for T10. The provider is OpenAI (the brief: challenge-*track* prizes require
OpenAI models), behind a provider-agnostic client. Pin model + prompt + schema; only credible,
open-access, PubMed-indexed journal text is ever sent.

The three jobs: Each is a service with a strict schema, a
deterministic validator *after* the model, and recorded responses for replay.

**Principle: the model proposes, code disposes.** The LLM never sets `source_type`, `status`,
`review_state`, scores, or IDs that weren't in its candidate list; it never writes a sentence the
validator can't tie to a claim.

## 0. Shared plumbing — `src/atlas/llm/`

- Interface: `LLMClient.parse(schema: type[BaseModel], system: str, input: str, model_tier: "fast"|"reasoning") -> BaseModel`.
  Services never import a vendor SDK. Adapter: `OpenAIClient` (`llm/openai_client.py`).
- **OpenAI adapter:** Chat Completions over plain HTTPS from the standard library (no vendor package),
  with strict structured output (`response_format: {type: "json_schema", strict: true}`; the Pydantic
  schema is made strict by `strict_schema`). Pydantic re-validates the returned JSON.
- **Models (env):** `OPENAI_MODEL_REASONING` (hypotheses, explanation) and `OPENAI_MODEL_FAST`
  (paper extraction). No model name is hard-coded; a missing name is an error, never a guess.
- **Refusals and cut-offs:** a `refusal` in the message raises `LLMRefusal` (the paper is marked
  "not extracted"); `finish_reason == "length"` is an error, never a partial parse.
- **Embeddings:** none. Search = exact + synonym + fuzzy over the ontologies.
- Cache/replay: key = sha256(provider, model, prompt version, input, schema name) →
  `data/cache/llm/<schema>/<key>.json`. Replay serves the cache; a live call happens only when the
  standing policy allows it and a key is set.
- Every result records provider, model and prompt version (`extraction_method` on each claim).
- Untrusted text (papers, researcher uploads) is passed inside clearly delimited blocks with an
  instruction that it is data, not instructions.
- Quotes are verified by our own substring check, never trusted from the model.

## 1. Extract — permitted passage → candidate `Claim`s

Used at **build time** (permitted passages, pipeline step 08) and **runtime** (lab uploads, T11).

```python
class ExtractedMention(BaseModel):
    text: str                                    # surface form as written
    entity_type: Literal["DISEASE","GENE","VARIANT","PHENOTYPE","MECHANISM","DRUG",
                         "STUDY","ASSET","PATIENT_ORG","INVESTIGATOR"]

class ExtractedClaim(BaseModel):
    subject: ExtractedMention
    predicate: Literal[...]                      # = ALLOWED_PREDICATES minus SIMULATES_WORKFLOW_FOR
    object: ExtractedMention
    observation_kind: Literal["reported_observation","computational_prediction","inference"]
    hedging: Literal["DEMONSTRATED","SUGGESTED","SPECULATED"]   # from the author's language
    context: ExtractedContext            # organism, tissue, assay/model, effect_direction, variant scope (nullable fields)
    supporting_quote: str                        # MUST be verbatim from the input
    contradiction_or_caveat: str | None

class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim]
    no_claims_reason: str | None
```

Post-processing (code, not model):
1. **Quote verification** — `source_span` must be an exact normalized substring of the passage,
   else the claim is quarantined with the reason.
2. **Resolve** each mention via the T03 resolver (§2). Unresolved stays unresolved — returned to
   the contributor for correction, never turned into a label-built ID.
3. **Set provenance in code:** `source_type` from the source record (published / database_record /
   lab_reported); uploads forced to lab_reported + unreviewed (existing `ingest_lab_finding`);
   `status` from `observation_kind` but `SPECULATED` hedging can only lower it to `inference`;
   strong causal predicates on inference are rejected by the existing `Claim` validator.
4. **Lineage:** claims from one paper/experiment share a `lineage_id`.
5. No LLM confidence anywhere (PLAN).

## 2. Reconcile — mention → candidate IDs (suggestions for the T03 resolver)

Pipeline for a mention string:
1. Exact match on label/synonym/xref index (MONDO, HGNC aliases, HPO synonyms, drug names).
2. Fuzzy (`rapidfuzz`, token-set ratio ≥ 90) → candidates.
3. (P1, T16) semantic retrieval — candidates only; embedding-only hits stay hypotheses.
4. If exactly one high-score candidate of the right type → accept. Else LLM chooses among
   **at most 8 candidates** (schema: `chosen_id: Literal[*candidate_ids, "NONE"]`, `rationale`).
   The dynamic `Literal` makes inventing an ID impossible.
5. Return `{resolved_id | None, candidates, method}` — the UI shows the method ("matched synonym
   'Batten disease'", "AI-suggested among 3 candidates — please confirm"). Ambiguous variants or
   transcript versions are never merged (PLAN T03); the user is asked to clarify.

## 3. Explain — claims → plain language

Input: the `ConnectionResult` / gap record and its claims (IDs, predicate, source_type, status,
review_state, context, quoted spans, contradictions, missing arrows); audience (`family` | `science`).
The model never gets unrestricted access to invent missing biological steps (PLAN).

```python
class ExplainedSentence(BaseModel):
    text: str
    claim_ids: list[str]          # must be ⊆ input claim ids, non-empty

class Explanation(BaseModel):
    sentences: list[ExplainedSentence]
    uncertainty_note: str         # what is NOT known along this path
```

Rules in the prompt + enforced by validator:
- Each sentence cites ≥1 input claim; sentences citing unknown IDs are dropped (count reported).
- **Grounding check:** gene/disease/drug names appearing in a sentence must belong to entities of the
  cited claims (string match against labels/synonyms). Fail → sentence dropped.
- **Status-aware verbs:** reported_observation + published "a study reported…"; database_record
  "a database lists…"; lab_reported "a lab has reported (not reviewed)…"; computational_prediction
  "a tool predicts…"; inference "this is a hypothesis…". Unreviewed claims never get "shown/proven".
  Validator checks prediction/inference sentences contain a hedge word.
- Missing channels/arrows must be mentioned as unknown, never omitted to make a path look complete.
- Output is labelled `cached` when replayed.
- Family audience: short sentences, no jargon without a gloss, target ~grade 7 reading level.
- No medical advice, no dosing, no prognosis. Appended disclaimer.

Precomputed at build for each claim and entity summary; live only for user-selected connections
(cached after first call).

## 4. Asset-reuse assessment & action drafting (reasoning model)

- Input: two diseases' structured facts (phenotype overlap w/ IC, onset ranges, mechanisms,
  asset `data_fields`, study eligibility text) — **structured data, not free web text**.
- Output = `AssetResult.reuse_limits` / `needs_expert_review` bullets, each citing claim IDs; same
  validator as Explain.
- Action drafts (outreach note, evidence brief) are template-first: code fills the facts, the model
  writes connective prose only, citations are footnotes to claims.

## 5. Safety & honesty guardrails (all services)

- Refuse/redirect: dosing, diagnosis, "should my child take X". UI returns a fixed message and points
  to clinicians + the patient org.
- Never name private individuals; investigators only via published professional affiliation.
- If inputs are insufficient → return a `GapResult`, not a creative answer.

## 6. Mini-evals (run before demo, results in README)

| Eval | Set | Metric | Target |
|---|---|---|---|
| Extraction precision | 15 passages, hand-labelled claims (report small n) | precision of accepted claims | ≥0.85 |
| Quote verification | all build extractions | % verified | 100% of displayed spans (unverified are quarantined) |
| Reconciliation | 40 mentions incl. synonyms/typos | top-1 accuracy | ≥0.9 |
| Explain faithfulness | 10 connections | % sentences grounded (auto) + manual spot-check | 100% auto, ≥9/10 manual |
| Refusal | 8 dosing/diagnosis prompts | correct refusal | 8/8 |

`scripts/evals/run_evals.py` prints a table; it's cheap to run and great for the team video.
