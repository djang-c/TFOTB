# Demo script (one-minute walkthrough and team video outline)

Status: a draft, not a recording. Every beat below was exercised in headless Chrome by `frontend/e2e/smoke.mjs` against the real API on 2026-10-04 (the lookup beat on a throwaway copy of the store). Before filming, run `make dev`, load the real reference data (`python scripts/fetch_ontologies.py`), and check each beat on screen yourself. If a beat does not match what you see, change the script, not the screen.

Seed cluster: CLN3 disease and Niemann-Pick disease type C (NPC). Seed paper: PMID 37245481 (cholesterol builds up in the lysosome in both diseases).

## One-minute walkthrough (about 170 spoken words)
| Time | Show | Say |
|---|---|---|
| 0:00 | Home page, type "CLN3", pick "neuronal ceroid lipofuscinosis 3" | "A family hears a rare diagnosis and asks: is anyone working on something related?" |
| 0:08 | Graph page, **Connections** tab, the Niemann-Pick type C row, "Show route" | "TFOTB lists related diseases and labels how strong the evidence is. Niemann-Pick type C is a literature-supported lead: both diseases store cholesterol in the lysosome, according to published papers. The route says 'shared feature, not a causal step'." |
| 0:22 | Click a citation chip to open the evidence drawer | "Every line opens its evidence: the exact sentence, a link to the paper's DOI, and who found it. Here an AI read the article. No human has reviewed it, and the page says so." |
| 0:34 | Open Niemann-Pick type C, **Overview**: "Hypotheses and treatment ideas" | "Treatment ideas are shown, but labelled hypothesis only, never a recommendation, with the passage, the paper and the reasoning." |
| 0:44 | Search a term nobody has searched (for example "ibuprofen" on a throwaway or reset store), press Enter | "If a term is new, it is checked against NLM MeSH and Europe PMC. A real medical term joins the catalogue with its papers. Anything else stays on this device only." |
| 0:54 | Simulation page, play the run | "Separately, a simulated robot checks a lab workflow. A pass says nothing about biology, and the page says so." |
| 0:58 | Footer line | "Research support only. No expert has reviewed these claims." |

## Video outline (about 3 minutes)
1. **The problem (15 s).** Finding and checking connections between rare diseases is slow, manual work. (Do not quote a statistic unless you have a source for it.)
2. **The automated part (50 s).** Show `scripts/ingest_papers.py --dry-run`: it finds credible papers by itself. Show a claim with its DOI link. Explain the checks: a PubMed-indexed journal article, a verbatim quote that names what it supports, a real ontology ID, and a citation taken from the paper's own record.
3. **Evidence labels (40 s).** Show the evidence categories, the "found by AI" and "AI hypothesis" labels, and independent studies versus papers that only restate a fact as background.
4. **No disease named (20 s).** Show the Symptoms page with "seizures, vision loss, ataxia": candidate diseases (the neuronal ceroid lipofuscinosis family appears) labelled as research hypotheses, not diagnoses.
5. **Honest gaps (15 s).** Show a gap card.
6. **The simulation (25 s).** Show one passing and one failing run (`blocked_path`), and the "not wet-lab validated" label.
7. **Limits (15 s).** Read the limits from the README out loud, including what is not built.

## Things not to say
- Do not call any result a finding, a diagnosis, a recommendation or "validated". Nothing has been reviewed by an expert.
- Do not say "peer reviewed" for the sources. Say "PubMed-indexed journal articles".
- Do not describe any similarity or coverage number as a probability or a confidence.
- Do not say the simulation shows a treatment would work.
- Do not call a replayed or recorded run live.
- Do not say the lookup "researched" a new term: it verified it against two public sources and listed papers. No claim was read from them.
- Do not claim OpenAI models were used: the stored claims were read by an earlier model from another vendor (see each claim's `extraction_method`). The OpenAI adapter exists but has not been run live.
- Do not claim a 10x speed-up. No milestone was measured.
- Do not present a name-only collaborator match as the same person.

## Pre-flight checklist
- [ ] `make test` passes on the filming machine.
- [ ] The real reference data is downloaded and the API serves real entities (not only SYNTHETIC demo ones).
- [ ] The seed paper is ingested, and its claims open in the drawer with a working DOI link.
- [ ] `backfill_papers.py` and `backfill_labels.py` have run (authors for the collaborator block; names such as "lysosome" instead of GO IDs).
- [ ] `make lint`, `make test` and `npm run e2e` (in `frontend/`) pass on the filming machine.
- [ ] For the lookup beat, use a store where the term has not been added yet (a verified lookup writes to `terms.jsonl`).
- [ ] The replay video plays, or the page's recorded replay is labelled as recorded.
