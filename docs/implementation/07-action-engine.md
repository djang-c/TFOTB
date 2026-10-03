# 07 — Action Cards, Gap Cards & Simulation Binding

Implements: T10, T17 (P1), T20–T24 binding. Follows PLAN "Action layer and automation boundaries":
every card has an evidence path, reuse limits, a next step, and a **responsible human**.

## 1. Card catalogue

| Priority | Kind | Audience | Content | Human boundary |
|---|---|---|---|---|
| **P0** | `evidence_brief` | both | Supported connection(s), per-channel vector, contradictions, missing evidence, open questions; exportable Markdown. This is the 10× measured artifact | Reviewer accepts the brief |
| **P0** | `outreach_note` | family | Sourced note to a **verified public contact** of a partner org/registry: why connected (cited), what to share, questions | User reviews and sends |
| **P0** | `asset_reuse` | both | Asset scope (model/tissue/assay/eligibility), access conditions, what differs, what needs expert review | Asset owner confirms suitability |
| **P0** | `gap_followup` | both | Gap kind, coverage, what information could change the result, who should review — **no invented experiment** | Named reviewer role |
| **P0** | `simulation_report` | science | Links an evidence-bound `ExperimentSpec` → MuJoCo run report + replay; scope label | Lab expert reviews any future physical protocol |
| P1 | `variant_evidence` | science | Normalized annotations, cited functional evidence, predictions (labelled), missing steps | Expert interprets mechanism; **no automatic LoF/GoF → modality routing** |
| P1 | `aso_checklist` | science | Dated checklist of n-Lorem's *published* criteria (link + retrieval date) with missing-information summary | Program + research physician determine eligibility |
| P1 | `repurposing_paths` | science | Reviewed drug–target–mechanism paths + unresolved safety/applicability questions | No prescribing, doses, or off-label safety claims |
| P1 | `phenopacket_example` | science | Synthetic case exported as validated Phenopackets example | No regulatory-grade claim |

## 2. Generation pattern

1. **Facts (code):** pull `ConnectionResult`s, claims, `AssetResult`s, `GapResult`, coverage.
2. **Template (Jinja2):** headings, footnote slots `[^c:<claim_id>]`, limitations, scope note.
3. **Prose (LLM, optional):** connective sentences only, through the Explain validator (doc 06).
4. **Render:** Markdown; frontend turns footnotes into chips that open the evidence drawer.
5. **Check:** all footnotes resolve; `responsible_human` present; denylist test for dosing /
   "eligible" / "should take" / "cure" language; cached-output label when replayed.

## 3. Gap card rules (PLAN "Coverage and honesty")

- Statement: "No supported route found in the indexed evidence as of <date>" — never "no
  treatment/registry exists".
- Kind ∈ insufficient coverage / unresolved identity / hypothesis only / conflicting evidence /
  supported research route.
- Coverage counts from the `CoverageManifest` (recorded operations).
- "What could change this" lists information types; it must not assert one assay will resolve it.
- Family copy: "We didn't find a supported connection yet. That's an answer too — here's what's
  missing and who could help check." Link to the upload flow for contributors (T11).

## 4. Robotics binding (existing code: `robotics/`)

Already DONE-verified (generic): scene, compiler, ledger, failure gates, report + replay.
Remaining (T20/T23):
1. `ExperimentProposal` drafted from a gap or connection: source claim IDs, research question,
   proposed assay/model, unresolved assumptions, `review_state`.
2. Human confirms → `ExperimentSpec.proposal_ref` gets the reviewed proposal ID (today:
   `generic_fixture_unreviewed`).
3. Persist `SimulationRun` record linked by `SIMULATES_WORKFLOW_FOR` (already excluded from
   biological support in `ranking.categorize`).
4. API `GET /api/simulations/{run_id}` + frontend `SimulationReplay` panel: report, checks
   (pass/fail/not_modeled), ledger before/after, recorded replay labelled "Recorded replay —
   workflow simulation only; not wet-lab validated".
5. Demo shows one valid run and one deliberate failure (`insufficient_volume` or `blocked_path`).

Opentrons adapter (T24) is P1 and compiles the *same* spec to a pinned protocol checked by the
Opentrons simulator, with its limits disclosed. Serial dilution only after separate bookkeeping
tests + wet-lab review (PLAN).
