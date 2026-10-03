# 01 — Scope, Demo Journey & 10× Milestone

Implements: PLAN "Goals", "Demo and submission", "The 10× hypothesis". Where this file and
`docs/PLAN.md` disagree, PLAN wins.

## 1. The bar (from the brief)

> Maria types her disease into one search box. The atlas follows it to a disrupted pathway, another
> gene, a related disease, and the patient group working on it. Every edge has an explanation and a
> source. Next, she discovers an existing registry and study design: the atlas shows what is
> reusable, what differs between the diseases, and which questions need expert review. Finally, she
> approaches a partner with a sourced proposal for shared research. If the graph reveals no
> supported lead, she leaves with a clear account of what is unknown and a next question to test.

## 2. Seed slice (T01, blocked on science review)

Workload targets from PLAN: **6–10 diseases, 10–20 curated variant/transcript findings, 20–40
claim-bearing source passages, 5–10 assets/organizations, 2 synthetic cases.**

**Candidate cluster to audit first:** neuronal ceroid lipofuscinoses anchored on CLN7 disease (gene
MFSD8; the Milasen n-of-1 ASO story), plus lysosomal neighbours (e.g. Niemann-Pick type C, CLN3,
neuronopathic Gaucher). This is a *candidate*, not a verified choice — T01 must confirm it has:

| Required fixture case (PLAN) | What we'd look for in this cluster |
|---|---|
| Useful positive route | Two differently-named diseases with a reviewed shared mechanism claim + a reusable registry/natural-history asset |
| Symptom-only connection | High phenotype overlap, no mechanism-channel support |
| Opposing-mechanism example | Same pathway, opposite effect direction → shared-treatment inference blocked |
| Missing-RNA case | Disease with no RNA findings → `availability: missing`, `score: null` |
| Uncertain variant | Synthetic VUS in MFSD8 with no functional evidence |
| Contradictory finding | Two claims that disagree, both visible |
| No-route result | Query that ends in an honest gap card |

If CLN7 can't supply a positive route + counterexample after T01, switch clusters — evidence
completeness beats the story.

## 3. Demo journeys

### Journey A — "Connection" (≈ 0–45 s of the 1-minute video)

| Step | Maria / Devon sees | Backed by |
|---|---|---|
| 1. Search | Types a disease, gene, or synonym → resolved entity, synonyms shown, ambiguity asks for clarification | ID resolver (T03), `/api/search` |
| 2. Summary | 3-sentence plain summary of what's known and what's missing | Grounded explanation over claims (doc 06) |
| 3. Related disease | Card shows **evidence category** ("reviewed mechanistic lead") and per-channel vector: phenotype ✓, DNA ✓, RNA *missing*, mechanism ✓ | `ConnectionResult` (T09) |
| 4. Inspect evidence | Drawer: claim, quoted source span, source type, status, review state, context, contradictions, lineage | Claim store (T02) |
| 5. Counterexample | A symptom-level lead clearly labelled "symptoms overlap; biology not shown to match" | Ranking gates |
| 6. Reusable asset + collaborator | Registry/study card with reuse limits, access conditions, public contact route — ranked separately from biology | Asset ranking (T10) |
| 7. Next step this week | Exported research-action brief / sourced outreach note; responsible human named | Action cards (T10, doc 07) |

### Journey B — "Honest gap" (≈ 45–60 s)

Synthetic MFSD8 VUS → "No supported route found in the indexed evidence as of <date>", the gap
type (insufficient coverage / unresolved identity / hypothesis only / conflicting), the coverage
manifest counts (from recorded operations), what information could change the result, and who
should review it. No fabricated experiment.

### Robotics segment

PLAN's walkthrough includes a short labelled **simulation replay** (MuJoCo) linked from the action
card, plus one deliberate failure (insufficient volume / blocked path). Always labelled "Workflow
simulation only; not wet-lab validated". Already built generically (T21–T22); needs binding to a
reviewed research question (T20/T23).

## 4. The 10× milestone

PLAN's milestone: **time to a reviewer-accepted collaboration/evidence brief** (supported connection,
reusable-asset assessment, contact route, unresolved questions), measured manual vs. Atlas-assisted
against the same quality rubric. Speedup = manual time ÷ assisted time; if it isn't 10×, we say so.

Our framing for the pitch: the brief is the first step toward **a patient group joining an existing
natural-history registry instead of building one from scratch.** Use it as narrative context only —
the claimed number is the measured brief speedup, not a registry-launch timeline.

Measurement plan (P0 for the pitch, small-n and disclosed):
- 2–3 brief tasks, each done manually and assisted, counterbalanced between the two builders.
- Record wall-clock, sources verified, reviewer corrections, failed attempts, and seed-curation
  effort (disclosed separately).

## 5. Non-goals (from PLAN, restated)

No diagnosis, prescribing, dosing, eligibility determination or treatment selection; no raw
sequencing; no real patient data; no physical robot execution; no all-disease coverage claims.
