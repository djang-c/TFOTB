# Demo script (team video outline and filming checklist)

The two 60-second submission videos (demo and tech), the project summary and the one-page report are in [`SUBMISSION.md`](SUBMISSION.md). This file has the longer team outline, what not to say, and the pre-flight checklist. Before filming, run `make dev`, load the real reference data (`python scripts/fetch_ontologies.py`), and check each beat on screen yourself. If a beat does not match what you see, change the script, not the screen.

Demo disease: CLN3 disease (*neuronal ceroid lipofuscinosis 3*, MONDO:0008767). It has paper claims and 35 related diseases, Niemann-Pick disease type C among them. Seed paper: PMID 37245481. Do not use Fabry disease for the evidence beat: it has no paper claims in the store.

## Video outline (about 3 minutes)
1. **The problem (15 s).** Finding and checking connections between rare diseases is slow, manual work. Don't quote a statistic without a source.
2. **The automated part (40 s).**
   - Show `scripts/ingest_papers.py --dry-run`: it finds credible papers by itself.
   - Explain the checks: a PubMed-indexed journal article, a verbatim quote that names what it supports, a real ontology ID, and a citation taken from the paper's own record.
   - Show a claim in the evidence drawer with its DOI link.
3. **Related diseases (30 s).**
   - Search CLN3 and open the dossier's **Related diseases**.
   - Filter by reason: shared gene, mechanism from papers, paper link, disease family, similar symptoms.
   - Point at the "found by AI" and "AI hypothesis" labels, and at independent studies versus papers that only restate a fact as background.
4. **Graph and clusters (25 s).**
   - In the second row, click **Graph**, then a node, then a link's evidence.
   - Click **Clusters** and read the explanation: diseases that share one specific thing with the searched disease, not a shared cause or treatment.
5. **No disease named (20 s).** On **Symptoms**, enter "seizures, vision loss, ataxia". The neuronal ceroid lipofuscinosis family appears among the candidate diseases, labelled as research hypotheses, not diagnoses.
6. **Coverage (10 s).** Open Fabry disease. No papers about it have been read yet, so its 34 related diseases come only from the reference data (disease family and similar symptoms), and each one is labelled as such. Don't say the page explains the gap: Fabry disease has no gap card.
7. **The experiment loop (30 s).**
   - On **Simulation**: the researcher's parameters, limits, pass criteria and rules.
   - The robot plan's checks, with one refused plan (for example 2 µL of DMSO stock in 100 µL, which is 2%, over the 1% limit).
   - **Run overnight (synthetic)** and the log, with every run labelled SYNTHETIC.
8. **Limits (10 s).** Read the limits from the README out loud, including what is not built.

## Things not to say
- Don't call any result a finding, a diagnosis, a recommendation or "validated". No expert has reviewed anything.
- Don't say "peer reviewed" for the sources. Say "PubMed-indexed journal articles".
- Don't describe any similarity or coverage number as a probability or a confidence. No claim has a confidence score.
- Don't say the simulation shows a treatment would work, or that its readings are real. The overnight run uses SYNTHETIC readings; measured results come only from readings the researcher uploads.
- Don't call a replayed or recorded run live.
- Don't say the lookup "researched" a new term. It checked the term against two public sources and listed papers; no claim was read from them.
- Don't say every claim was read by GPT. Each claim's drawer names the model that read it; show a GPT-5 mini claim if you show the model.
- Don't claim a measured 10x speed-up. The **10× case** page is arithmetic on stated assumptions (11.5× for a group waiting on a shared robot, 6.2× for a lab with its own). Say that, not a result.
- Don't present a name-only collaborator match as the same person.

## Pre-flight checklist
- [ ] The gate in `SUBMISSION.md` is done (store packaged).
- [ ] `make lint`, `make test` and `npm run e2e` (in `frontend/`) pass on the filming machine.
- [ ] The real reference data is downloaded and the API serves real entities, not only SYNTHETIC demo ones.
- [ ] The seed paper is ingested, and its claims open in the drawer with a working DOI link.
- [ ] `backfill_papers.py` and `backfill_labels.py` have run, so the collaborator block has authors and names such as "lysosome" show instead of GO IDs.
- [ ] The CLN3 dossier lists related diseases. The first load takes about 8 s, so open it once before filming.
- [ ] The Simulation page's overnight run finishes and shows its log.
