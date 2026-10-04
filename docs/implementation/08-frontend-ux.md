> **Superseded 2026-10-04.** The frontend was rebuilt as a TanStack Start single-page app (React, Vite, Tailwind, three.js) on the real API; see `frontend/README.md` and `docs/DECISIONS.md`. This file describes the earlier Next.js design and is kept for its UX principles.

# 08 — Frontend & UX

Implements: T12 (explorer + evidence inspector), UI parts of T10, T11, T23. PLAN: "React with a
search-first interface, evidence drawer, optional graph canvas, and Markdown action export."
Brief principles: **low ink, high signal · one global search · progressive reveal · explain every
edge · patient action view**.

## 1. Information architecture

```
/                    One search box; example chips; one-line value prop; dataset/version footer
/entity/[id]         Main experience
/about               How it works, evidence labels explained, 10× method, sources, limitations panel
```

`/entity/[id]`:
```
┌ Header: search · [Family | Science] view · dataset badge · "cached output" indicator ───────────┐
├ Main column (summary-first) ───────────────────────────┬ Drawer (on demand) ─────────────────────┤
│ Plain summary + what's missing                         │ Evidence drawer for a claim/connection: │
│ Q1 Who shares our characteristics?                     │  predicate · source type · status ·     │
│    ConnectionResult cards: category pill +             │  review state · quoted span + link ·    │
│    channel chips (phenotype ✓ DNA ✓ RNA — mech ✓)       │  context · contradictions · lineage     │
│ Q2 What useful work already exists?                    │  (siblings = same experiment)           │
│    AssetResult cards + collaborators (separate list)   │ or Simulation report + recorded replay  │
│ Q3 What should we do together next?                    │                                          │
│    P0 action cards · gap card when applicable          │                                          │
│ [Show graph] → optional canvas                         │                                          │
└────────────────────────────────────────────────────────┴──────────────────────────────────────────┘
```
The three brief questions are the literal section headings.

## 2. Visual encoding (see doc 03 §3 for the mapping)

| Meaning | Encoding |
|---|---|
| Evidence category | Pill: reviewed mechanistic lead (teal), symptom-level lead (slate), hypothesis only (purple outline), conflicting evidence (amber ⚠), insufficient coverage (grey) |
| Channel availability | Chip per channel: ✓ available (score + definition on hover), — missing ("no data", never 0), ✕ incompatible, ! failed |
| Claim status | solid = reported observation; dashed = computational prediction; dotted purple = inference |
| Source type / review | Badges: Published · Database record · Lab-reported (yellow) · SYNTHETIC (always visible) · Unreviewed · Reviewed ✓ · Disputed ⚠ |
| Blocked shared-treatment inference | Inline note: "Opposite effect direction — shared treatment not supported; research connection still shown" |
| Node types (canvas) | Disease teal · Gene/variant blue · Mechanism violet-grey · Phenotype slate (low-IC faded) · Drug amber · Organization rose · Asset/study green |

Never color-only: every encoding has text/shape. Contrast ≥ 4.5:1.

## 3. Optional graph canvas

`@xyflow/react` + `elkjs` layout in a web worker; ≤ 40–60 nodes from `/entities/{id}/graph`;
"+N more" aggregate nodes; click edge → evidence drawer for its claim; hover dims non-neighbours.
Cut before the evidence drawer if time is short (PLAN: canvas optional).

## 4. Components

`SearchBar` (synonym shown, ambiguity prompt) · `SummaryCard` · `ConnectionCard` +
`ChannelChips` · `EvidenceDrawer` · `AssetCard` · `CollaboratorList` · `ActionCard` (this-week
sentence, responsible human, .md download) · `GapCard` · `UploadPanel` (structured finding →
preview unresolved IDs / missing fields → confirm; result shows Lab-reported + Unreviewed) ·
`SimulationReplay` (report, checks, ledger, labelled recorded video) · `GraphCanvas` (optional) ·
`LimitationsPanel` · `ViewToggle` · `DatasetBadge`.

Footnote chips in any Markdown body open the drawer for that claim — "explain every edge" applies
to prose too.

## 5. Data access

`src/lib/api.ts` typed client on generated `api.gen.ts`; `NEXT_PUBLIC_MOCK=1` serves
`data/fixtures/*.json` so UI work doesn't block on the backend. Loading skeletons; inline errors;
failed channels shown as "!" not hidden.

## 6. Accessibility & copy

Keyboard-navigable search/drawer/cards; focus trap in drawer; list alternative to the canvas;
responsive to 390 px. Family view: no unexplained acronyms (glossary tooltips). PLAN success
check: users can tell observations from hypotheses — test copy with someone outside the team.
