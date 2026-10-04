# Demo script (one-minute walkthrough and team video outline)

Status: a draft written from the code and tests, not from a recording. Before filming, run `make dev`, load the real reference data (`python scripts/fetch_ontologies.py`) and ingest at least the seed paper, then check every beat below on screen. If a beat does not match what you see, change the script, not the screen.

Seed cluster: CLN3 disease and Niemann-Pick disease type C (NPC). Use the seed paper (PMID 37245481): in both diseases cholesterol builds up in the lysosome.

## One-minute walkthrough (about 150 spoken words)
| Time | Show | Say |
|---|---|---|
| 0:00 | Search box, type "CLN3" | "A family hears a rare diagnosis and asks: is anyone working on something related?" |
| 0:08 | CLN3 disease page, the related diseases list | "TFOTB lists related diseases and labels how strong the evidence is. Niemann-Pick type C appears." |
| 0:18 | Click a citation to open the evidence drawer on the lysosome claim | "Every line opens its evidence. This one says: found by AI in this article, with the sentence quoted word for word and a link to the paper." |
| 0:30 | Point at the "not reviewed by a human" note and the AI hypothesis label on the pathway claim | "Nothing waits for a human to approve it. Instead each claim says where it came from. This one is an AI hypothesis, not a finding." |
| 0:42 | A page with no supported connection (the gap card) | "When it finds nothing it says so, with a date and what it searched. It never says no connection exists." |
| 0:50 | Simulation page, play the replay | "Separately, a simulated robot checks a lab workflow. A pass says nothing about biology, and the page says so." |
| 0:58 | Limits line | "Research support only. No expert has reviewed these claims." |

## Video outline (about 3 minutes)
1. **The problem (20 s).** Researchers spend most of their time finding and checking connections by hand.
2. **The automated part (50 s).** Show `scripts/ingest_papers.py --dry-run`: it finds credible papers by itself. Show a claim with its DOI link. Explain the four checks: a PubMed-indexed journal article, a verbatim quote, a real ontology ID, and a citation taken from the paper's record.
3. **Evidence labels (40 s).** Show the evidence categories, the AI-hypothesis label, and independent studies versus papers that only restate a fact as background.
4. **Honest gaps (20 s).** Show a gap card.
5. **The simulation (30 s).** Show one passing and one failing run (`blocked_path`), and the "not wet-lab validated" label.
6. **Limits (20 s).** Read the limits from the README out loud.

## Things not to say
- Do not call any result a finding, a diagnosis, a recommendation or "validated". Nothing has been reviewed by an expert.
- Do not say "peer reviewed" for the sources. Say "PubMed-indexed journal articles".
- Do not describe the symptom-similarity number as a probability or a confidence.
- Do not say the simulation shows a treatment would work.
- Do not call a replayed or recorded run live.

## Pre-flight checklist
- [ ] `make test` passes on the filming machine.
- [ ] The real reference data is downloaded and the API serves real entities (not only SYNTHETIC demo ones).
- [ ] The seed paper is ingested, and its claims open in the drawer with a working DOI link.
- [ ] The frontend builds (`make lint` includes the type check). This has not been run since the origin labels were added.
- [ ] The replay video plays, or the page's recorded replay is labelled as recorded.
