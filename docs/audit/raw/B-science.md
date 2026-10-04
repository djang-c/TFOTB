# Audit B: Scientific integrity and grounding (TFOTB)

Auditor: Agent B (skeptical scientific reviewer). Read-only audit of `/Users/jang/Documents/startup-research/hackathon/tfotb`.
Audit date: 2026-10-03 (store timestamps are 2026-10-04 UTC). No repo file was edited except this report; scratch scripts live under `/private/tmp/claude-501/-Users-jang/`.
Labels used: `VERIFIED` (I ran/read it), `UNVERIFIED` (could not check offline), `PREDICTION`/`HYPOTHESIS` where relevant. This is an audit of software behaviour and of the quote-to-claim fit; it is not a biological validation of any claim.

## 1. Executive verdict: CONDITIONALLY READY

No fabricated evidence and no clinical directive was found in the stored data. The core safety design holds: quotes are code-checked verbatim at ingest, hypotheses must cite stored claims, hypothesis-only predicates cannot be `reported_observation`, and simulations cannot change a category. The data-vs-hypothesis labelling works end to end for the one stored AI hypothesis.

The project is not ready to claim "cross-checked, sourced evidence" without these changes:

1. 6 of 58 paper-extracted claims (10.3%, Wilson 95% CI 4.8% to 20.8%) are wrong or overreach; 9 more are partial. Nothing in code checks that a quote entails the triple.
2. Contradiction handling is dead code. `contradicting_claim_ids` and `Claim.contradicts` are never set, so `conflicting_evidence` is unreachable, and opposite-direction effects still rank as "literature-supported lead".
3. The API and UI state false things about the evidence ("No other claim from this experiment group is indexed"; "Evidence from papers is not extracted yet"; stored-claim `contradicting_claims` hard-coded to `[]`).
4. The one stored AI hypothesis restates a link that paper PMID:37245481 already states (the duplicate guard misses it because JNCL is split across two MONDO IDs). It cites a claim whose quote does not support it. The "no paper states it" framing is therefore not accurate.
5. The paper-extracted claims never reach the ranking, the evidence brief or the entity page. "Literature-supported lead" cannot occur on live data.

Severity counts: Critical 0, High 4, Medium 8, Low 5.

## 2. Method and scope

- All 59 stored claims (58 paper claims plus 1 AI hypothesis) were audited, which is a census rather than a random sample (N=59 > 25). Source: `data/store/atlas.db`, table `claims`, opened `mode=ro`. Dump scripts live in the session scratchpad (`dump.py`, `lab.py`).
- Quote verbatim check: only `data/cache/texts/PMID-37245481.txt` is cached (1 of 34 ingested or attempted papers). All 8 claims of that paper were confirmed verbatim with the project's own `_squash` normalisation. For the other 50 paper claims the source text is not on disk, so verbatim presence is `UNVERIFIED` here (ingest code enforces it at `src/atlas/extraction.py:152`, and I did not re-fetch: no network). I judged entailment from the stored quote alone.
- DOI/URL correctness: the DOIs come from fetch metadata. The cached text contains no DOI, and I did not use the network. All 20 or so DOIs are `UNVERIFIED`. The pattern is plausible for each journal (EBioMedicine, Glia, iScience and others).
- Entity IDs were checked against the pinned MONDO/HGNC/ChEBI/GO files through the project's own `Resolver` (labels printed in the table). Some PMIDs are in the 42xxxxxx range, beyond my own knowledge; I treat them as pinned data and cannot independently confirm they exist.
- Negative-case scripts: `/private/tmp/claude-501/-Users-jang/neg.py`, `real.py`, `real2.py` (run with `PYTHONPATH=src`, `Settings(_env_file=None)` so `.env` was not read; no server started; no model calls).

## 3. Claim audit (all N=59)

Verdict key: OK = quote states the claim as written; OK-m = supported with a minor wording or scope caveat; PARTIAL = quote supports only part, or the framing is shaky; WRONG = not entailed or mis-scoped or wrong predicate. IDs shortened to the last 10 characters. Disease/gene labels were checked against the pinned ontologies.

| Claim (CLAIM:PMID-...) | Triple (labels via ontology) | Verdict | Note |
|---|---|---|---|
| 37245481-b4b6c0d454 | CLN3 GENE_ASSOC NCL3 (MONDO:0008767) | OK | verbatim verified; "caused by mutations in CLN3"; scope background correct |
| 37245481-10fd203a20 | NPC1 GENE_ASSOC NPC | OK | verbatim verified; positive-control statement |
| 37245481-3d479d5098 | NPC2 GENE_ASSOC NPC | OK | verbatim verified |
| 37245481-4071f16807 | NCL3 ACCUMULATES cholesterol in lysosome | OK | verbatim verified; own finding (new_finding) correct. Caveats not stored: autopsy DLPFC, n=5 JNCL, n=4 NPC, n=6 controls (paper methods) |
| 37245481-4d01fc4fdb | NCL3 ACCUMULATES cholesterol in late endosome | OK | same quote, split by compartment, as designed |
| 37245481-02a5ef5fa4 | NPC ACCUMULATES cholesterol in late endosome | OK | positive control; scope background defensible |
| 37245481-f9ad0e2e8a | NPC ACCUMULATES cholesterol in lysosome | OK | same |
| 37245481-e7ed59984e | NCL3 SHARES_PATHWAY NPC | WRONG (scope) | "Our findings also support that JNCL and NPC share pathogenic pathways" is the paper's own conclusion, stored as `scope: background`; should be `new_finding`. Status `inference` is right |
| 41466111-a128df5653 | PPT1 GENE_ASSOC NCL1 | OK | |
| 41982147-9035f60e55 | NPC1 GENE_ASSOC NPC | OK-m | quote names "primarily caused by mutations in the NPC1 gene"; disease from context |
| 41982147-9ca14b63a2 | NPC2 GENE_ASSOC NPC | OK | |
| 41982147-aba49610fd | NPC ACCUMULATES cholesterol in late endosome | PARTIAL | quote says "lipid accumulation" and "cholesterol transport"; "cholesterol" as the accumulating substance is an inference; lysosome half not emitted |
| 42011986-65c4e5ecd4 | SPP1 GENE_ASSOC NPC (mouse microglia, up) | WRONG | an expression change in Npc1-/- mice is not a gene-disease association; own finding stored as `scope: background`; quote is cut mid-sentence ("...particularly in the PN60"); mouse `Spp1` stored under a human HGNC ID |
| 42016609-0745b6d2a9 | CLN3 GENE_ASSOC JNCL (MONDO:0019262) | OK-m | JNCL here maps to MONDO:0019262, not 0008767 (see F7) |
| 42016609-14c199f5d9 | JNCL ACCUMULATES cholesterol in lysosome | OK-m | quote: "majority of the lipid component is cholesterol" in lysosomal storage material; ID 0019262 |
| 42016609-bad8103a47 | CLN3 GENE_ASSOC JNCL | OK-m | "gene defective in this form of Batten disease, CLN3" |
| 42036217-79e2fdea9c | arimoclomol CANDIDATE_THERAPY NPC | OK-m | quote: FDA-approved; predicate and `inference` status understate an approval (see F8) |
| 42036217-cc70ffac7a | NPC1 GENE_ASSOC NPC | OK | |
| 42036217-e5f9eee444 | NPC2 GENE_ASSOC NPC | OK | |
| 42036217-eed3dc15f4 | miglustat CANDIDATE_THERAPY NPC | OK-m | "licensed disease-modifying therapy"; same understatement |
| 42037350-1a40f5d0cd | NPC2 GENE_ASSOC NPC | OK | |
| 42037350-429faa960c | NPC1 GENE_ASSOC NPC | OK | |
| 42146023-1af1397c7f | gemfibrozil AFFECTS_TRANSCRIPT CLN2 (mouse, increase) | OK-m | quote starts "Previously, we have demonstrated"; second-hand citation of the authors' own earlier work. The predicate is a strong causal one, ok for a perturbation, but there is no assay or dose context |
| 42163273-2651f3d761 | CLN3 GENE_ASSOC JNCL | OK | |
| 42206050-2178e2b067 | TARDBP GENE_ASSOC ALS | PARTIAL | quote is about TDP-43 protein aggregation, not a genetic association |
| 42206050-3bc2a92706 | TARDBP GENE_ASSOC FTD | PARTIAL | same |
| 42206050-3f6d8c9ddd | MAPT GENE_ASSOC Alzheimer disease | WRONG | the quote names "tau protein and amyloid-b" aggregation; the gene MAPT and a genetic association are not stated |
| 42256287-053395c029 | NPC1 GENE_ASSOC NPC | OK | |
| 42256287-7b9e7219c3 | NPC ACCUMULATES cholesterol in lysosome | OK | "multi-tissue accumulation of unesterified cholesterol ... within late endosomes/lysosomes" |
| 42376638-25a636fc2e | NPC1 GENE_ASSOC NPC | OK | |
| 42376638-398a505345 | NPC2 GENE_ASSOC NPC | OK | |
| 42376638-8a46a7c5ee | arimoclomol CANDIDATE_THERAPY NPC | OK-m | approved (US, aged 2 years or more, with miglustat); F8 |
| 42376638-a91c282914 | NPC ACCUMULATES cholesterol in lysosome | WRONG | quote: "Activation of the CLEAR network is thought to enhance lysosomal performance and decrease the accumulation of cholesterol within lysosomes". It states a hedged mechanism of CLEAR activation; it does not state that NPC accumulates cholesterol. It is also cited by the stored AI hypothesis |
| 42432889-18f098d72b | NPC1 GENE_ASSOC NPC | OK-m | single proband, compound heterozygous NPC1 variants; a case finding (own result) stored as `background` |
| 42432889-1e88f03886 | ATP7B GENE_ASSOC Wilson disease | OK | off-topic for the NPC/CLN3 atlas, but correct |
| 42432889-4807e0f01b | NPC1 GENE_ASSOC NPC | OK | |
| 42432889-51bfe80f2f | ATP7A GENE_ASSOC Menkes | OK | off-topic but correct |
| 42432889-c2c1b714f5 | NPC2 GENE_ASSOC NPC | OK | |
| 42438645-1eaafe7961 | NPC1 GENE_ASSOC NPC | OK | |
| 42438645-239e16e6e8 | NPC ACCUMULATES cholesterol in lysosome | WRONG | quote: "NPC is a rare AR lysosomal storage disorder caused by pathogenic variants in NPC1 and NPC2". The word cholesterol (the substance field) is not in it. The model supplied the substance from background knowledge, which the prompt forbids |
| 42438645-6f265d246c | NPC1 GENE_ASSOC NPC | OK-m | patient-level variants (c.3019C>G, c.3104C>T), case report; scope `background` |
| 42438645-b02c294444 | NPC2 GENE_ASSOC NPC | OK | |
| 42438645-cf0f6b4700 | SMPD1 GENE_ASSOC ASMD | OK | |
| 42467639-0ca08ecb83 | NPC1 GENE_ASSOC NPC | OK | |
| 42467639-89c8ee80f0 | NPC2 GENE_ASSOC NPC | OK | |
| 42467639-e7d691dbda | arimoclomol CANDIDATE_THERAPY NPC | PARTIAL | quote: "TFEB activation has recently been proposed as a mechanism of action for ... arimoclomol". It is about mechanism, and the therapy claim rests on the clause "newly approved NPC drug" |
| 42585307-e39be3bd23 | NPC1 GENE_ASSOC NPC | OK | |
| 42616279-139181ab46 | RFC1 GENE_ASSOC CANVAS | OK-m | repeat expansion for diagnosis |
| 42616279-4d12cc7b55 | FMR1 GENE_ASSOC FXTAS | OK | |
| 42616279-8af5b18aeb | COQ8A GENE_ASSOC CoQ10 deficiency | PARTIAL | quote is a concatenated table row ("Coenzyme Q10 deficiencySQ9019M3NM_020247.5(COQ8A):c.1228C > T..."), patient-level, not a readable statement |
| 42616279-cb026301f2 | SETX GENE_ASSOC AOA2 | PARTIAL | same table-row artefact |
| 42616279-e9f24d88af | FXN GENE_ASSOC Friedreich ataxia | WRONG | quote "Seventeen of them were molecularly diagnosed as FRDA cases." names no gene. FXN matches only through the old HGNC alias symbol "FRDA" (a disease abbreviation) |
| 42620532-c11d6900d4 | N-acetyl-L-leucine (CHEBI:17786) CANDIDATE_THERAPY multiple sclerosis | PARTIAL | hedged speculation ("may represent ... if further substantiated") and off-topic. "NALL" and "MS" are abbreviations, and the text is not cached, so the identity of the compound and the isomer is `UNVERIFIED` |
| 42794762-172ef5a3c7 | miglustat CANDIDATE_THERAPY NPC | OK-m | "established clinical benefit"; F8 |
| 42794762-26eef4151b | GLB1 GENE_ASSOC GM1 gangliosidosis | OK | |
| 42794762-57d3118dba | MCOLN1 GENE_ASSOC mucolipidosis IV | OK | |
| 42794762-b14ed41449 | NPC2 GENE_ASSOC NPC | OK | |
| 42794762-f9f72d0906 | NPC1 GENE_ASSOC NPC | OK | |
| AIM:HYP-441387f494 | NPC SHARES_PATHWAY JNCL (0019262) | see F2 | labelled AI hypothesis correctly; grounding defects below |

Tally of the 58 paper claims: WRONG 6 (e7ed59984e, 65c4e5ecd4, 3f6d8c9ddd, a91c282914, 239e16e6e8, e9f24d88af); PARTIAL 9 (aba49610fd, 2178e2b067, 3bc2a92706, e7d691dbda, 8af5b18aeb, cb026301f2, c11d6900d4, and the two case-report scope items 18f098d72b and 6f265d246c); OK or OK-m 43.

- Strict error rate: 6/58 = 10.3% (Wilson 95% CI 4.8% to 20.8%).
- Error plus partial: 15/58 = 25.9%.
- 4 further claims (arimoclomol x2, miglustat x2) are correctly quoted but mis-framed as "candidate therapy / hypothesis" (F8).
- Scope label (`context.scope`): 2 wrong in 58 (e7ed59984e and 65c4e5ecd4, both own findings stored as background). The two case-report items are ambiguous. All other scopes were consistent with their quotes.
- Entity resolution: no wrong gene symbol or ontology label was found. The problems are semantic: the JNCL split (F7), a protein-to-gene jump (MAPT), and the FRDA alias.
- Sampling caveat: the first-paper-heavy store (13 papers restate NPC1/NPC2 to NPC) makes the error rate dominated by the review-style statements. The rate does not generalise to full-text experimental claims.

## 4. Findings

### F1. High: nothing in code checks that a quote entails the triple
- Where: `src/atlas/extraction.py:150-190` (`_reject_reason`). It checks that the quote is in the text, the predicate and types, and that mentions resolve. It does not check that the subject, object or `substance` appear in the quote, nor that the direction/hedge is kept. Stored `scope` is a model guess ("when unsure choose background").
- Evidence: 42438645-239e16e6e8 (cholesterol absent from the quote), 42616279-e9f24d88af (no gene in the quote), 42376638-a91c282914 (a different proposition), 42011986-65c4e5ecd4 (wrong predicate and scope), 42206050-3f6d8c9ddd. Table section 3.
- Proposed fix: add a deterministic post-check that each resolved mention (or a registered alias or abbreviation defined in the paper) occurs in the quote, quarantining otherwise. Add a second, independent entailment pass (a different model, or a rule check) with an explicit entails/not-entails verdict stored on the claim. Do not promote the "Found by AI ... checked word for word" label to "checked" for entailment. The UI text only claims verbatim matching, which is accurate, but a reader will infer more.

### F2. High: the stored AI hypothesis is not what its text says, and its guard is weak
- Where: `src/atlas/hypotheses.py:121-145` (`_reject_reason`), stored `CLAIM:HYP-441387f494`.
- Evidence (VERIFIED, `data/store/ingest_log.jsonl` last line and the claim row):
  - Text: "Separate papers report lysosomal storage ... in JNCL, and ... in NPC. This points to a possible shared defect". The model first proposed NPC to MONDO:0008767 and was rejected "already stored" (the paper 37245481 states exactly this, claim e7ed59984e). It then re-proposed with MONDO:0019262, the broader JNCL term, which passed. The result duplicates a published statement and presents it as new.
  - `derived_from` includes `CLAIM:PMID-42376638-a91c282914`, whose quote does not state NPC cholesterol accumulation (section 3).
  - The guard only requires that the two entities occur at some end of any cited claims. It does not require the cited claims to share a feature (compartment plus substance) that links the two diseases. Reproduction (`neg.py` N6): two unrelated claims, one per disease, pass.
  - `_CLINICAL` is a tripwire. All of these pass: "Patients with NPC should be treated with miglustat.", "We recommend administering arimoclomol to JNCL patients.", "Give miglustat twice daily.", "This proves CLN3 causes NPC-like disease and is a cure." (`neg.py` N6). The stored rationale is itself benign ("This needs testing by comparing ...").
- Label survival (VERIFIED): `source_type=ai_generated`, `status=inference`, `knowledge_level=prediction`, `derived_from` set; the drawer, hover preview and evidence brief print "AI hypothesis, not a finding". `ranking.categorize` ignores hypothesis-only predicates (N5: "hypothesis only").
- Fix: dedupe hypotheses against paper-stated claims after collapsing equivalent disease IDs (F7), including parent and child. Require every cited claim to pass an entailment check. Require a shared feature in the cited claims. Extend the clinical-language filter (recommend, treat with, should be treated, give, administer, cure, proves, causes). Add a bounded-verbs allowlist for rationale ("may", "could be tested").

### F3. High: contradiction handling does not exist in practice
- Where: `src/atlas/schemas.py:182,236`, `src/atlas/ranking.py:53`, `src/atlas/channels/claims.py:103-110`, `src/atlas/api/routes.py:344-349`.
- Evidence (VERIFIED by `grep`): `contradicting_claim_ids` and `Claim.contradicts` are never assigned anywhere under `src/atlas`. `EvidenceCategory.conflicting_evidence` and the gap kind `conflicting_evidence` are therefore unreachable. In the API `lineage_siblings` and `contradicting_claims` are hard-coded `[]` for every stored claim, so the "Disagrees with" drawer section can never appear for real data.
- Reproduction (`neg.py` N3): two diseases with opposite effect direction ("increase" vs "decrease") on the same compartment and substance are still categorised "literature-supported lead", with only a flag `molecular_mechanisms:effect_direction`. `BLOCKING_MISMATCHES` only switches `shared_treatment_inference_allowed` off; it does not demote the category. Direction is compared as a free-text string, so "increase" vs "upregulated" (same meaning) also flags a mismatch (false positive), and "decrease" vs "reduced" would too.
- The real corpus contains an explicit counter-statement that was not captured: PMID:37245481 line 89 ("A recent report failed to show a lysosomal cholesterol accumulation in human JNCL fibroblasts"). The claim `4071f16807` therefore shows no contradiction, and its tissue (brain) vs fibroblast context difference is not represented.
- Fix: populate `contradicts` at extraction (a "contradicts or fails to replicate" statement type) and in the channel (same subject, predicate, object with opposite normalised direction). Normalise direction to an enum. Make an opposite direction or a contradicting claim demote the category to `conflicting_evidence`. Wire the API to compute `contradicting_claims` and `lineage_siblings` from the store.

### F4. High: false or misleading statements to the reader
- Evidence (VERIFIED):
  1. `src/atlas/api/routes.py:330-336` returns `lineage_siblings: []` for stored claims. The drawer then prints "No other claim from this experiment group is indexed." (`frontend/src/components/EvidenceDrawer.tsx`, the Lineage section). For claim 4071f16807 there are 7 other claims with the same `lineage_id`. The statement is false.
  2. `frontend/src/app/page.tsx:204` ("Evidence from papers is not extracted yet") and `frontend/src/app/entity/[id]/page.tsx:116-120` ("No claims have been extracted from papers for this entry yet ... this entry has simply not been read") when the store holds 58 claims from 19 papers about exactly the seed entities. The home text is shown unconditionally.
  3. `EvidenceDrawer.tsx` meaning(): "Recorded as a hypothesis only, never as a finding" is shown for approved-drug statements (F8).
  4. `GET /api/meta` returns the demo's `claims: 26` and the `SYNTHETIC` banner. The real store size (59 claims, 19 productive papers, 30 ingested and 4 skipped sources, 55 quarantined statements) is not reported by any endpoint.
- Fix: compute siblings and contradictions from the store, replace the two "not extracted yet" strings with counts from the store, and add a `/meta`-level real-store block (papers ingested, skipped with reason, quarantined, claims by predicate and scope).

### F5. Medium (High for the brief): extracted evidence is disconnected from ranking and from the briefs
- Where: `src/atlas/search.py:112-128` registers only the phenotype channel and gene-level `dna_variants` over HPO `genes_to_disease`. The paper store (`atlas.db`) is read only by `/graph`, `/routes` and `/claims`.
- Evidence (VERIFIED, `real.py`): for MONDO:0008767 and MONDO:0018982 `connections` returns categories {symptom-level lead: 13, hypothesis only: 2} and {symptom-level lead: 12}; 0 paper claim IDs appear in any ranking; `/entities/{id}` returns `claims: []`; the evidence brief's "Known claims" lists a single HPO claim for NCL3. The category "literature-supported lead" (`ranking.py:70-78`) cannot occur on live data, only in unit tests and the synthetic demo.
- Consequence: the product's central evidence-quality story (qualified leads) is not exercised by the real data, and the brief says nothing about the 58 extracted claims or that they were excluded.
- Fix: either feed the store's claims into the channels (after F1/F3), or state plainly in the brief and coverage manifest that paper-extracted claims are shown only in the graph and drawer and are not used for ranking.

### F6. Medium: graph routes and the "hypothesis only" flag
- `src/atlas/graph.py:97-104`: a hop is hypothesis-only only if every claim on it has status `inference`.
  - N1 (VERIFIED): a hop that holds an AI hypothesis plus an observed claim reports `hypothesis_only=False`; the AI claim is listed but the flag hides it.
  - N2 (VERIFIED): a path made of `computational_prediction` claims (`HAS_PREDICTED_RNA_EFFECT`, or a `SIMULATES_WORKFLOW_FOR` link) reports `hypothesis_only=False`. Latent today (no such claims in `atlas.db`), but a prediction or simulation hop would be presented as "observed or reported steps" (`cards.py:151`).
- Hub nodes: `GET /entities/MONDO:0008767/routes?to=MONDO:0018982` returns "supported" non-hypothesis routes through `GO:0005764` (lysosome) or `GO:0005770`. `HGNC:2074 -> HGNC:7897` (CLN3 to NPC1) returns a 4-hop route through the two diseases and the lysosome. A generic organelle node connects every lysosomal disease; the route hides the substance, so "route exists" reads as a mechanistic link. The route response omits `scope` (own finding vs background) and `source_type` per hop.
- `/routes` gap uses `coverage_manifest_id="COV:none"` (`graph.py:84`, default), which is a dangling reference, not a recorded manifest. The gap statement itself is scoped and dated ("up to 4 steps ... as of 2026-10-04"), which is honest.
- Fix: treat any hop whose claims are not all `reported_observation` from a credible source as hypothesis-only (or show a per-hop provenance mix). Exclude compartment and other generic hub nodes from path search, or require the same substance on both sides.

### F7. Medium: entity identity is split and aliases can overreach
- `data/aliases.json` maps "JNCL" to MONDO:0008767 only for source PMID:37245481 (owner choice). All other papers resolve "JNCL" and "Batten disease" to the broader MONDO:0019262 (VERIFIED, `real2.py`). So CLN3-gene and cholesterol claims for "JNCL" are split between two nodes (0008767 and 0019262), the seed cluster entity page for 0008767 does not show the other 4 JNCL claims, and the duplicate guard of F2 fails.
- `CLN3 disease` itself returns suggestions only; `NPC` is ambiguous (nasopharyngeal carcinoma) without the alias file. This is honest in public search. The extraction resolver relies on an owner-approved, not expert-reviewed alias list.
- HGNC alias "FRDA" resolving to FXN (finding in section 3) shows that disease abbreviations can match gene alias symbols.
- Variants: no variant-level claims exist (`dna_variants` is gene-level only by design, `claims.py:107` note). Case-report variants (c.2932C>T etc.) are not parsed; `c.2932C>T` and `p.Arg978Cys` do not resolve. That is honest, but the UI never says "variant-level evidence is absent".
- Fix: add a parent/child (is_a) equivalence step before duplicate and independence checks and in the entity page; disallow gene resolution from a mention that the paper uses as a disease name.

### F8. Medium: drug and treatment framing
- `CANDIDATE_THERAPY_FOR` is hypothesis-only and stored as `inference` even when the paper states an approval (arimoclomol, miglustat). The label "treatment idea (not a recommendation)" and "Recorded as a hypothesis only, never as a finding" (UI) misdescribe a quoted regulatory fact, and the quoted approval carries no date or jurisdiction check (regulatory status statements age).
- `hide_drug_claims` is `false` in `config/ingest_policy.json`, so drug claims are in the graph and the API by default. The safety wording is good ("not a recommendation"), and the evidence brief has `_CLINICAL` guards, but see the weakness in F2.
- The off-topic MS claim (N-acetyl-L-leucine) is hedged speculation in the paper and appears as a candidate therapy node.
- Fix: add a separate predicate or status for "approved or licensed (per source, date)", or show approval claims as source statements. Keep a `treatment idea` label only for speculative statements. Record the source date.

### F9. Medium: independence counting and review-heavy corpus
- `lineage_id` is `STUDY:PMID-<n>`, i.e. paper-level, not experiment-level. Two publications of the same experiment (preprint plus journal, or a case series reported twice) count as 2 independent lineages (`neg.py` N4: `independent_support_count = 2`). One paper that reports several experiments counts as 1 (conservative).
- `background_support_count` rewards repetition: 13 papers restate "NPC1 causes NPC" and show as 13 background lineages. Review papers cite one another, so restatements are not independent. The ranking uses this count as a tie-breaker (`connections.py:94-103`).
- A "literature-supported lead" can rest solely on `background`-scope claims (N5), and a tissue mismatch does not demote it (N5). The category name suggests more than "a review sentence repeated it".
- Fix: add a cross-paper dedupe (same authors, title and DOI relations: preprint to version of record), and require at least one `new_finding` claim for "literature-supported". Show the background and independent counts side by side (partly done already).

### F10. Medium: freshness, coverage disclosure and missing-RNA honesty
- All 58 claims have `published_at=null` and `retrieved_at=null`; the only extraction timestamp is `ingest_log.jsonl` (2026-10-04). The drawer prints published and retrieved dates only when present, so no date is shown for any paper claim. Ontology versions are disclosed (CHECKSUMS notes, MONDO/HPO v2026-09-01, GO release 2026-07-26), which is good. The coverage manifest's `retrieved_at` is the query time, not data age; `dataset_version` is the string "pinned-ontologies".
- Coverage counts are built from recorded operations (`search.py:279-297` tallies of HPO rows: fetched 16099, screened 15462; paper ingest counts come from the ledger), so no count is generated text (VERIFIED). But the paper-ingest coverage is not exposed on any endpoint, and 4 papers were skipped for size (`text is 78725..115284 chars, over the 70000 cap`; later policy raised the cap to 120,000 and the log does not show a re-run) plus 2 network failures later retried. The reader cannot see that.
- RNA: no RNA channel is registered in the live registry (`search.py:127-128`), so the coverage manifest lists only `dna_variants` and `phenotype`. "No RNA evidence" is shown by omission, not as a labelled missing channel. In the brief, missing data is shown correctly where a channel exists ("dna_variants: missing | missing: claims:MONDO:0012188"; `ChannelComparison` forbids a score when missing, `schemas.py:~245`).
- "No supported route" is honest and scoped (type, step bound and date), except the dangling `COV:none` id.
- Fix: store `published_at` (from PubMed) and `retrieved_at` per claim, disclose the 4 skipped papers and the cap in the coverage view, and list registered-but-absent evidence types (RNA, variant-level) in the manifest as "not modelled".

### F11. Medium: one stale row takes down the evidence views
- `src/atlas/api/claimstore.py:25-29` catches only `OSError` and `sqlite3.Error`. A row that fails `Claim` validation (for example `schema_version` 0.1.0, reproduced in `real2.py`) raises `pydantic.ValidationError`, so `/entities/{id}/graph`, `/routes` and `/claims/{id}` return HTTP 500. A missing store returns the ontology graph without paper claims and the STORE label dropped, which is fine.
- Fix: validate row by row, skip and count invalid rows, and report the count in the response.

### F12. Low: smaller labelling gaps
- Graph edge hover for an AI hypothesis reads "may share a disease process with. Click for evidence." (`Graph3D.tsx`); only the line colour (purple) marks `inference`, and a paper-stated inference looks identical to an AI hypothesis. The drawer is correct once opened. Add "AI hypothesis" to the edge label when `source_type` is `ai_generated`; the graph edge payload lacks `source_type`.
- `context.scope` is shown as a raw key/value in the drawer; there is no explanation of "new finding vs background", and edge style does not use it.
- Mouse genes are stored under human HGNC IDs with `organism: mouse` in context (Spp1/SPP1). Ranking channels do not read `organism`, so a mouse-only observation can contribute to a human lead (not currently reachable, since F5).
- Quotes can be truncated mid-sentence (65c4e5ecd4), losing qualifiers. The prompt asks for hedges to be copied, and the verbatim check passes any substring.
- `data/store/snapshot` (58 claims) is stale versus `atlas.db` (59): it lacks `CLAIM:HYP-441387f494`. If the deployed API reads the snapshot, the AI hypothesis is absent; if it reads the db, they differ. UNVERIFIED which one deploy uses.

### F13. Low: simulation invariants rest on omission
- VERIFIED safe today: `ranking.categorize` drops `SIMULATES_WORKFLOW_FOR` (`ranking.py:64-69`; N5 returns "hypothesis only" for a simulation-only mechanism channel). `SimulationRun` refuses to exist unless biology and physical execution are `not_modeled` and the scope label says "not wet-lab validated" (`simulation.py`). The link claim is `computational_prediction`, `synthetic_fixture`, unreviewed, and no channel reads that predicate. Simulation specs and runs are generic synthetic fixtures (not for real diseases, per the route comment).
- Weakness: the guarantee exists only in `categorize`. `independent_support_count`, `reviewed_support` and `background_support_count` count any claim ID in `path_claim_ids`, so if a future channel added a simulation claim, the tie-breakers would count it (and a `reviewed` sim claim would add reviewed support). The graph path flag has the same hole as F6. Fix: filter `SIMULATES_WORKFLOW_FOR` and `computational_prediction` claims in `build_result` rather than only in `categorize`, and add a test.

### F14. Low: tripwires are not guarantees
- `_CLINICAL` (`schemas.py:~563`) covers dose, mg, prescribe, "should take/start/stop", eligible. It does not cover recommend, treat with, administer, give, cure, proves, "is effective". Card text is template-generated and the clinical regex only guards templates and hypothesis rationale; it is not a safety proof.

## 5. Items that held up (tested)

- Fabricated citation in a hypothesis: rejected ("cites claims that are not stored", N6).
- A hypothesis cannot cite another hypothesis, an upload, or a fixture (`_observed`, `hypotheses.py`), and an AI claim never reaches "literature-supported lead" (N5).
- Missing data is not zero: a channel without data returns `missing` and `score=None`; the schema forbids otherwise (VERIFIED in `schemas.py` and the real brief).
- `lab_reported` unreviewed claims cannot make a lead (N5 -> "hypothesis only").
- Source failure: ingest records failures in `ingest_log.jsonl`; a failing channel yields `availability: failed` (`channels/base.py:55-62`); a missing store gives an empty claim set, not an invented one.
- Ambiguous names stay ambiguous in public search ("NPC": 3 candidates; "CLN3 disease": suggestions only).
- UI: synthetic demo data is labelled at API level (`_synthetic`) and in the home page.
- Review is a label, not a gate: the UI says "Not reviewed by an expert" on every claim (VERIFIED in `meaning()`).

## 6. Negative-case summary (real code)

| Case | Result |
|---|---|
| Missing RNA evidence | No RNA channel in the live registry; absent from coverage, not shown as "missing" (F10) |
| Opposing effects, same target | Still "literature-supported lead", flag only; `conflicting_evidence` unreachable (F3) |
| Ambiguous variant identity | Variants not modelled; unresolved, quarantined or ignored; not disclosed in UI (F7) |
| One experiment published twice | Counted as 2 independent lineages (F9) |
| Relevant-looking but unsupported citation | A fabricated ID is rejected; a real ID whose quote does not support the claim (a91c282914) is accepted and cited by the AI hypothesis (F1, F2) |
| Model hypothesis shown as an established cause | Not possible in the UI/cards (label present); the hypothesis text itself can contain recommendation language that the tripwire misses (F2, F14) |
| Source/API failure | Ingest and channel failures are recorded; a stale row yields HTTP 500 (F11) |
| Simulation mistaken for biology | Cannot change category (F13); hop flag hole (F6) |

## 7. Limitations the project must disclose

1. Claims are LLM-extracted, single-pass, unreviewed, and only verbatim-checked. About 10% (CI 5% to 21%) of the 58 audited claims are wrong and about 26% have a defect. Use "found by AI, quote verified, meaning not verified".
2. Only 20 or so papers (19 with claims), newest open-access PubMed articles in discovery order (`sort_date:y`), not a systematic or exhaustive review; 4 papers skipped for length. Review and case-report heavy; recency bias; no retraction re-check after ingest.
3. Association only. `GENE_ASSOCIATED_WITH_DISEASE` includes pathology-level and case-report statements. "NPC1 causes NPC" is stored as an association (OK), but the UI predicate "is linked to" is weaker than some quotes ("caused by"), which is the safe direction.
4. No variant-level, RNA, or quantitative effect-size data, and no sample sizes in stored claims. Samples in the key paper are small (JNCL n=5, NPC n=4, controls n=6) and come from autopsy brain only.
5. Species: mouse observations are stored under human gene IDs.
6. Hypotheses are model outputs (claude-opus-5-5, prompt hypothesis-v1) from a handful of claims; a single one exists. They are not evidence.
7. Treatment statements are literature statements, not recommendations; regulatory status is as of the paper date, not today.
8. Phenotype similarity (HPO, BMA-Lin) is a display-only similarity, not evidence of a shared cause; the UI says so.
9. Ontology equivalence (JNCL and CLN3 disease) is an unreviewed owner decision.
10. Robotics simulation is kinematic only; biology and physical execution are not modelled; it is not wet-lab validated.
11. Counts of "independent studies" are paper-level and do not account for shared authorship, shared cohorts or citation chains.

## 8. UNVERIFIED items

- Verbatim presence of 50 of 58 quotes (source texts not cached) beyond the ingest-time check.
- Every DOI/source URL (no network use; the cached text holds none).
- Existence and content of the 42xxxxxx-range PMIDs and the claims in them (beyond the quote).
- Whether the deployed API reads `atlas.db` or the stale snapshot.
- The identity of "NALL" (CHEBI:17786 N-acetyl-L-leucine) and "MS" in PMID 42620532 (source text not cached).
- Frontend behaviour beyond reading the source (no browser run, no server started).
- Test-suite status (I did not run `pytest`; and "tests pass" would not establish scientific correctness anyway).
