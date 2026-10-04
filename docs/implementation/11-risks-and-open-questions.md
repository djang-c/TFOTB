# 11 — Risks & Open Questions

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| T01 blocked: no one available for expert evidence review | High | High | Time-box T01 to H3; proceed with `unreviewed` labels and disclose; category tops out at "hypothesis only" without review |
| Chosen cluster lacks a positive route + counterexample | Med | High | Decide at H3 gate; switch cluster rather than stretch evidence |
| Graph canvas looks like a hairball | High | Med | Canvas is optional (PLAN); summary + drawer first; caps + ELK layout |
| LLM latency/rate limits during live judging | Med | High | Record/replay cache; all demo calls pre-recorded |
| Hallucinated IDs / quotes leak into UI | Med | Critical | `validate_curie`, resolver, quote verification, quarantine, dynamic-Literal suggestions |
| Investigator name collisions create false "shared KOL" | Med | Med | ≥2 papers + affiliation/ORCID match; show papers on both sides |
| Medical-advice perception (dosing, prognosis) | Low | Critical | No dosing anywhere; refusal tests; disclaimers |
| Overclaimed 10× | Med | Med | Measured brief speedup only, small n disclosed (PLAN) |
| PLAN assumes 4 contributors; we are 2 | Certain | High | Explicit cuts in doc 09; robotics core already done |
| **Track-prize eligibility: brief says challenge-track prizes require OpenAI models** | Certain | High (prize-only) | OpenAI is the only provider, behind the provider-agnostic `LLMClient` |
| The model refuses some biomedical text | Low–Med | Med | Check the `refusal` field, mark the paper "not extracted", log refusal rate |
| Toolchain setup on Builder B's Mac (no Node, system Python 3.9) | High | Med | Install Node 22 + pnpm + Python 3.12 first; reuse `requirements.lock` |
| Scope creep | High | High | Cut list in doc 09; feature freeze H19 |

## Proposed decisions (from Builder B's planning session — need teammate agreement in this PR)

| Topic | Proposal | Conflicts with |
|---|---|---|
| LLM provider | OpenAI (`OPENAI_MODEL_REASONING`, `OPENAI_MODEL_FAST`) via provider-agnostic `atlas.llm` | — |
| Team | 2 builders, roles + cuts in doc 09 | PLAN assumes 4 |
| API + frontend | FastAPI inside `src/atlas/api`; Next.js in `frontend/` | PLAN says "React" — compatible |
| 10× narrative | Measured brief speedup (PLAN) framed as the first step to joining an existing natural-history registry | Compatible |

Resolved in favour of PLAN (our earlier plan changed): no 4-tier provenance, no numeric
confidence, no weighted composite score, no automatic LoF/GoF → modality routing, MuJoCo P0 with
Opentrons as P1 adapter.

## Open questions

1. Who can do the T01 evidence review? (Blocking for "reviewed" labels.)
2. Is CLN7 / NCL + lysosomal neighbours the cluster to audit first?
3. OpenAI key availability (for the adapter / track prizes)?
4. Hosting: Vercel + Render/Fly OK?
5. When does the 24h clock start / submission deadline?
6. **HPO commercial-use terms** — read the HPO licence directly or ask the HPO team before the phenotype channel ships (audit could not settle it).
7. Which Databricks APIs do we have (LLM serving, compute, Delta)? Public data only; each outbound use needs approval.
8. Is there a licensed, non-identifiable imaging dataset for any ViT work? If not, no imaging model (doc 12 §3).
9. Does the graph-model channel (T26) have time, or is it cut? Without a leakage-controlled evaluation we make no accuracy claim.
