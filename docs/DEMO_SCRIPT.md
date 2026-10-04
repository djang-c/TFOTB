# Demo script (one-minute walkthrough and team video outline)

Status: a draft written from the code, the tests and API responses, not from a recording. The data beats below were checked against the running API on 2026-10-04 (see `QUALITY_AUDIT.md`). The screen beats were NOT: the frontend was not built or viewed in the audit. Before filming, run `make dev`, load the real reference data (`python scripts/fetch_ontologies.py`), ingest the seed paper and run the two backfill scripts (README), then check every beat on screen. If a beat does not match what you see, change the script, not the screen.

Seed cluster: CLN3 disease and Niemann-Pick disease type C (NPC). Seed paper: PMID 37245481 (cholesterol builds up in the lysosome in both diseases).

## One-minute walkthrough (about 160 spoken words)
| Time | Show | Say |
|---|---|---|
| 0:00 | Search box, type "CLN3" | "A family hears a rare diagnosis and asks: is anyone working on something related?" |
| 0:08 | CLN3 disease page, the related-diseases list | "TFOTB lists related diseases and labels how strong the evidence is. Niemann-Pick type C is listed as a literature-supported lead: both diseases store cholesterol in the lysosome, according to published papers." |
| 0:20 | Click a citation to open the evidence drawer | "Every line opens its evidence: the exact sentence, a link to the paper, and who found it. Here, an AI read the article. No human has reviewed it, and the page says so." |
| 0:32 | The evidence brief's route list, then the collaborators block | "It shows how the diseases connect, and which researchers published on both. Matches by name alone are marked unverified, and authorship is not a contact." |
| 0:44 | A page with no supported connection (the gap card) | "When it finds nothing it says so, with a date and what it searched. It never says no connection exists." |
| 0:52 | Simulation page | "Separately, a simulated robot checks a lab workflow. A pass says nothing about biology, and the page says so." |
| 0:58 | Limits line | "Research support only. No expert has reviewed these claims." |

## Video outline (about 3 minutes)
1. **The problem (15 s).** Finding and checking connections between rare diseases is slow, manual work. (Do not quote a statistic unless you have a source for it.)
2. **The automated part (50 s).** Show `scripts/ingest_papers.py --dry-run`: it finds credible papers by itself. Show a claim with its DOI link. Explain the checks: a PubMed-indexed journal article, a verbatim quote that names what it supports, a real ontology ID, and a citation taken from the paper's own record.
3. **Evidence labels (40 s).** Show the evidence categories, the "found by AI" and "AI hypothesis" labels, and independent studies versus papers that only restate a fact as background.
4. **No disease named (20 s).** Show `/symptoms` with "seizures, vision loss, ataxia": candidate diseases (the neuronal ceroid lipofuscinosis family appears) labelled as research hypotheses, not diagnoses.
5. **Honest gaps (15 s).** Show a gap card.
6. **The simulation (25 s).** Show one passing and one failing run (`blocked_path`), and the "not wet-lab validated" label.
7. **Limits (15 s).** Read the limits from the README out loud, including what is not built.

## Things not to say
- Do not call any result a finding, a diagnosis, a recommendation or "validated". Nothing has been reviewed by an expert.
- Do not say "peer reviewed" for the sources. Say "PubMed-indexed journal articles".
- Do not describe any similarity or coverage number as a probability or a confidence.
- Do not say the simulation shows a treatment would work.
- Do not call a replayed or recorded run live.
- Do not claim OpenAI models were used: every stored claim came from an Anthropic model. The OpenAI adapter exists but has not been run.
- Do not claim a 10x speed-up. No milestone was measured.
- Do not present a name-only collaborator match as the same person.

## Pre-flight checklist
- [ ] `make test` passes on the filming machine.
- [ ] The real reference data is downloaded and the API serves real entities (not only SYNTHETIC demo ones).
- [ ] The seed paper is ingested, and its claims open in the drawer with a working DOI link.
- [ ] `backfill_papers.py` and `backfill_labels.py` have run (authors for the collaborator block; names such as "lysosome" instead of GO IDs).
- [ ] The frontend builds and type-checks (`make lint`). This has not been run since the origin labels, collaborator block and symptoms page were added.
- [ ] The replay video plays, or the page's recorded replay is labelled as recorded.
