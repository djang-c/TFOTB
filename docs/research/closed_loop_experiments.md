# Closed-loop (overnight) assay experimentation: evidence and data-model notes

Date: 2026-10-04. Status: EXPLORATORY literature review, not a systematic review. Written for the TFOTB "Simulation" tab redesign.
Location note: the requester asked for `docs/research/closed_loop_experiments.md`; the evidence-specialist role may only write under `research/evidence/`, so the file lives here. Move it by hand if wanted.
Not clinical advice. Research planning only.

Verdict legend: VERIFIED = I opened the source and the passage supports the claim. UNVERIFIED = only a search-result snippet or my background knowledge; do not cite as fact. DESIGN = my proposal, not a finding.
Access caveat: NCBI/PubMed pages returned captcha/cookie walls to the fetch tool. Bibliographic data for PubMed items came from Europe PMC REST (opened). Assay Guidance Manual (AGM) chapters were opened via the `/sites/books/` path.

## 1. Typical early-stage plate assay on a liquid handler

| # | Claim | Source (opened) | Location | Type | N | Verdict |
|---|---|---|---|---|---|---|
| 1.1 | Common plate formats 96 (12x8) / 384 / 1536; 96-well ~250-300 uL capacity, 384/1536 ~75-100 uL ("use less reagents") | AGM, Basics of Assay Equipment and Instrumentation for HTS, https://www.ncbi.nlm.nih.gov/sites/books/NBK92014/ | plate/format passage | guideline chapter | n/a | VERIFIED (as stated on page; the 75-100 uL figure is quoted as the page gives it) |
| 1.2 | Hand pipette usable range 100 nL to 1 mL; solenoid dispensers deliver >0.1 uL; dispensing a nominal volume across a whole plate takes 1-3 min | same | liquid handling section | guideline | n/a | VERIFIED |
| 1.3 | Plate colour by readout: clear = absorbance, white = luminescence (less crosstalk, reflects signal), black = fluorescence | AGM, Microplate Selection and Recommended Practices, https://www.ncbi.nlm.nih.gov/sites/books/NBK558077/ | plate colour section | guideline | n/a | VERIFIED |
| 1.4 | Covers may be unnecessary for assays of minutes to a few hours (little evaporation) | same | evaporation/covers | guideline | n/a | VERIFIED |
| 1.5 | Detection modes: absorbance (light absorbed), fluorescence (emission after illumination), luminescence (light from a chemical/biochemical reaction) | NBK92014 | detection section | guideline | n/a | VERIFIED |
| 1.6 | Compounds are delivered at fixed concentrations in 100% DMSO, so DMSO compatibility must be tested early; 0-10% DMSO typically tested; later validation uses the DMSO concentration planned for screening | AGM, HTS Assay Validation, https://www.ncbi.nlm.nih.gov/sites/books/NBK83783/ Sec. 2.3. The "0 to 10%" wording is from a search snippet, only the first half opened | Sec. 2.3 | guideline | n/a | VERIFIED (solvent compatibility); "0-10%" UNVERIFIED |
| 1.7 | Cell viability example protocol uses 0.2% final DMSO; tetrazolium assays limited to ~1-4 h reagent incubation; ATP (luminescent) assay "most sensitive, less prone to artifacts"; uneven luminescence can come from temperature gradients, uneven seeding, edge effects | AGM, Cell Viability Assays, https://www.ncbi.nlm.nih.gov/sites/books/NBK144065/ | assay-specific sections | guideline | n/a | VERIFIED |
| 1.8 | Enzyme assays: run in initial-velocity region (<10% substrate depleted or product formed); substrate at or near Km to detect competitive inhibitors; background from no-enzyme or no-substrate wells | AGM, Basics of Enzymatic Assays for HTS, https://www.ncbi.nlm.nih.gov/sites/books/NBK92007/ | initial velocity; kinase background | guideline | n/a | VERIFIED |
| 1.9 | Edge effect quantified: unwrapped VWR 96-well plates showed 34+/-2% (corner) and 35+/-3% (outer) lower metabolic activity vs centre, 25+/-5% second row, 10+/-5% third row; Greiner plates 26+/-4% corner, 16+/-8% outer; a perimeter-buffer plate cut it to 13+/-8% / 10+/-9% (n.s.) | Mansoury et al. 2021, PMC8024881 https://pmc.ncbi.nlm.nih.gov/articles/PMC8024881/ | results | experiment, one cell line/assay | N not extracted | VERIFIED for the numbers; generalisation across assays UNVERIFIED |
| 1.10 | Positional (plate-position) effects and replicate measurements matter for primary-screen hit calling | Malo et al. 2006 Nat Biotechnol, DOI 10.1038/nbt1186, PMID 16465162 (Europe PMC abstract) | abstract | methods paper | n/a | VERIFIED (abstract only) |
| 1.11 | Opentrons OT-2 GEN2 ranges: P20 1-20 uL, P300 20-300 uL, P1000 100-1000 uL; Flex 1/8-ch 1-50 and 5-1000 uL, 96-ch 1-200 and 5-1000 uL. Do not use tips larger than pipette max. Flex well-bottom clearance default 1 mm for aspirate/dispense | https://docs.opentrons.com/python-api/pipettes/loading/ and /characteristics/ | model table; "tips" note | vendor docs | n/a | VERIFIED |
| 1.12 | Autoprotocol/Strateos container types carry well_volume_ul, dead_volume_ul, safe_min_volume_ul (e.g. 40 uL well, 2-5 uL dead, 3-15 uL safe min) | search-result snippet only; the container_type page returned 404 | n/a | vendor docs | n/a | UNVERIFIED |

Not found in any opened source (do not state as fact): typical working volumes per assay step (e.g. 5-20 uL in 384 low-volume plates), standard layouts (columns 1-2 / 23-24 controls, 32 control wells per 384 plate), "max 0.5-1% DMSO" rules of thumb, tip-reuse policies. All UNVERIFIED; the researcher must enter these per assay and instrument. Note the AGM 3-day plate-uniformity design uses interleaved Max/Mid/Min wells (Sec. 3.2.1, VERIFIED, NBK83783) rather than a fixed edge layout.

## 2. Acceptance / quality criteria

| # | Claim | Source | Location | Type | Verdict |
|---|---|---|---|---|---|
| 2.1 | Z-factor, Zhang JH, Chung TDY, Oldenburg KR. J Biomol Screen 1999, DOI 10.1177/108705719900400206, PMID 10838414. Reflects dynamic range and data variation; "suitable for assay quality assessment" | Europe PMC abstract (opened) | abstract | methods paper | VERIFIED |
| 2.2 | Formula Z = 1 - 3(s1+s2)/abs(m2-m1); categories: 1 ideal; 1 > Z >= 0.5 excellent; 0.5 > Z > 0 doable; 0 yes/no; <0 screening essentially impossible. The citing authors say the cutoffs lack theoretical justification | Bioinformatics 36(22-23):5299, https://academic.oup.com/bioinformatics/article/36/22-23/5299/6042703 (secondary report of Zhang) | intro | secondary | VERIFIED as reported by this secondary source; original table not opened |
| 2.3 | AGM plate acceptance: Z' >= 0.4 (comparable to signal window SW >= 2) on all plates; CV of each signal (Max, Mid, Min) <= 20% | NBK83783 Sec. 3.2.2 | Sec. 3.2.2 | guideline | VERIFIED |
| 2.4 | AGM validation = 3-day plate-uniformity study + replicate-experiment study; replicate-experiment pass = MSR < 3 and both limits of agreement between 0.33 and 3.0 | NBK83783 Sec. 1, 4.7 | as listed | guideline | VERIFIED |
| 2.5 | Relative IC50 = parameter c of the 4-parameter logistic (midpoint between fitted plateaus). Reportable only with at least 2 concentrations beyond each bend point; absolute IC50 needs at least 2 concentrations predicted <50% and 2 >50%. Sebaugh, Pharm Stat 2011, DOI 10.1002/pst.426, PMID 22328315 | Europe PMC abstract | abstract | guideline paper | VERIFIED |
| 2.6 | For Hill slope 1.0, 10% to 90% inhibition spans an 81-fold concentration range (so a plateau-reaching series needs about 2 log10 units around IC50) | AGM chapter "Validating Identity, Mass Purity and Enzymatic Purity of Enzyme Preparations", https://www.ncbi.nlm.nih.gov/books/NBK91995/ | inhibitor studies | guideline | VERIFIED (arithmetic check: 9^2 = 81, consistent) |
| 2.7 | Hill slope far from 1 can flag stoichiometric/tight-binding or artefacts; "minimum 10 concentrations for IC50"; conversion at 80% shifts IC50 up to 3-fold | search snippet only (AGM / J Med Chem 2025 acs.jmedchem.4c02052 returned 403) | n/a | n/a | UNVERIFIED |
| 2.8 | "Z' >= 0.6 in 384-well, 0.7 when possible; revisit if <0.5" | search-snippet summary only | n/a | vendor/blog | UNVERIFIED |

Conflict to surface in the UI: AGM accepts Z' >= 0.4, Zhang's "excellent" starts at 0.5, and the 2020 critique questions all cutoffs. The tool must therefore make the threshold researcher-defined, with 0.5 only as a suggested default (DESIGN), and print the threshold used next to every pass/fail.

What "failed run" means in practice (DESIGN, synthesised from 2.3-2.6; no single source defines it). Distinguish: (a) technical failure: instrument/geometry/volume/tip error, missing reads, control CV > limit, Z' below threshold, drift or edge pattern; the data say nothing about biology and the run is re-done; (b) assay failure: signal window too small, no plateau, Hill slope outside range, fit not converged, CI too wide, vehicle control off baseline; (c) scientific negative: assay valid (QC passed) but compound inactive. Only (c) is a result. Rules must never treat (a)/(b) as a negative.

## 3. Choosing the next experiment

| # | Claim | Source | Location | Type | Verdict |
|---|---|---|---|---|---|
| 3.1 | Adam (2004 robot scientist): system "originates hypotheses, devises experiments, physically runs them using a laboratory robot, interprets results to falsify hypotheses, then repeats"; intelligent experiment selection beat cheapest and random selection with cost decreases of 3-fold and 100-fold. King et al., Nature 2004, DOI 10.1038/nature02236, PMID 14724639 | Europe PMC abstract | abstract | primary, one yeast system | VERIFIED |
| 3.2 | King et al., Science 2009, "The automation of science", DOI 10.1126/science.1165620, PMID 19342587: Robot Scientist Adam autonomously generated and tested functional-genomics hypotheses in yeast; conclusions confirmed manually; 6.6 million biomass measurements | Europe PMC abstract | abstract | primary | VERIFIED. (My first PMID guess 19246277 was wrong, correct is 19342587) |
| 3.3 | Eve: integrates library screening, hit confirmation and lead generation via cycles of QSAR learning and testing; economic modelling says AI compound selection beats standard screening; TNP-470 found as potent P. vivax DHFR inhibitor. Williams et al., J R Soc Interface 2015, DOI 10.1098/rsif.2014.1289, PMID 25652463 | Europe PMC abstract | abstract | primary + modelling | VERIFIED (claims are the authors') |
| 3.4 | Mobile robot chemist ran autonomously 8 days, 688 experiments, 10-variable space, batched Bayesian search; mixtures 6x more active than start. Burger et al., Nature 2020, DOI 10.1038/s41586-020-2442-2, PMID 32641813 | Europe PMC abstract | abstract | primary, materials not biology | VERIFIED |
| 3.5 | SDL = automated experiments integrated with data-driven decision making; Bayesian optimisation "maximize or minimize some black-box function ... of controllable experimental parameters" using a surrogate and acquisition function balancing exploration/exploitation; autonomy levels; Adam and Eve cited as drug-discovery/biology examples; safety "requires additional research". Tom et al., Chem Rev 2024;124(16):9633, PMC11363023 | opened | review | review | VERIFIED |
| 3.6 | Emerald Cloud Lab protocols are code (Symbolic Lab Language; experiment functions such as ExperimentAbsorbanceIntensity with Method/Instrument options; ALCOA+ metadata) and Strateos/Lilly remote lab; Strateos "closed-loop" claims | search snippets only | n/a | vendor | UNVERIFIED (not opened) |
| 3.7 | Factorial / response-surface DOE for assay optimisation (e.g. DMSO, enzyme, substrate, incubation as factors) | AGM enzymatic chapter lists DMSO as a factor in optimisation experiments (opened, NBK92007); named DOE methods (full factorial, central composite) are background knowledge | n/a | n/a | PARTIAL: DOE-for-assays existence VERIFIED only as "factors evaluated"; method names UNVERIFIED |

Typical "if it fails, tweak X" rule types. These are DESIGN proposals consistent with 2.3-2.6, not sourced prescriptions; researchers should own the values.

| Condition (evaluated on QC/fit outputs) | Allowed tweak (within researcher bounds) |
|---|---|
| No lower or upper plateau (fewer than 2 points beyond a bend, Sebaugh 2.5) | extend top and/or bottom concentration by a set factor, up to the allowed max / solubility / DMSO limit |
| Hill slope outside the researcher's range | flag only; re-run with replicates; no automatic tweak |
| Signal window or S/B low, Z' below threshold | raise enzyme/cell number, substrate, or incubation time within range, one factor per run |
| Signal saturating or >10% conversion (enzyme) | lower enzyme or shorten incubation |
| Control CV above limit | re-run unchanged first; then check tips/mixing/volumes |
| Edge pattern detected | move controls/test wells off the outer ring or use buffer wells |
| Vehicle (DMSO) control deviates from untreated | lower final DMSO % |
| Volume below pipette minimum or above tip capacity | change dilution scheme or intermediate plate, never the volume limit itself |
| IC50 CI too wide | add concentrations near the midpoint or replicates |

## 4. Safety / integrity practices

| # | Claim | Source | Verdict |
|---|---|---|---|
| 4.1 | Replicates are needed to verify assumptions and reliable hit calling | Malo 2006 abstract (1.10) | VERIFIED |
| 4.2 | Formal within-run variability and assay-comparison study before use (replicate-experiment study, MSR < 3) | NBK83783 | VERIFIED |
| 4.3 | Adam recorded experiments in an ontology/logical language so every result links to its logical description (reproducibility) | King 2009 abstract | VERIFIED |
| 4.4 | ECL/Strateos audit trails, 21 CFR Part 11 style controls | not opened | UNVERIFIED |
| 4.5 | SDL review: safety of robotic labs needs more research | Tom 2024 | VERIFIED |

Recommended controls (DESIGN, none are cited findings): optimiser can only propose values inside researcher-declared range/step/allowed-set; every proposal is checked by a validator against hard instrument limits before dispatch and rejected otherwise; one adaptation rule fires per factor per iteration and is logged with the triggering metric; max iterations, max reagent/plate budget, and stop-on-N-consecutive-technical-failures; a hit is not "confirmed" until independent replicate runs (researcher sets N, e.g. 2) each pass QC and agree in potency (e.g. within a researcher-set fold); an append-only log of definition version hash, run inputs, raw reads, QC values, rule fired, and proposed next run; any request outside bounds stops the loop and asks a human. The AI proposes, rules constrain, a validator enforces.

## 5. Recommended data model (DESIGN, for the Simulation tab)

```
ExperimentDefinition {
  id, version, hash, owner, created, assay_type: dose_response|enzyme|viability|optimisation
  plate: { format: 96|384, plate_type, well_volume_max_uL, well_volume_min_uL, readout: abs|fluor|lumi, wavelength_nm? }
  layout: { controls: [{name: positive|negative|vehicle|blank, wells|rule, n_replicates}], edge_policy: exclude|buffer|randomise, randomisation_seed }
  parameters: [{ name, kind: continuous|discrete|categorical|ordinal, unit,
                 role: varied|fixed, min, max, step, allowed_values?, scale: linear|log,
                 default, max_change_per_iteration? }]
  fixed_constraints: { dmso_max_pct, final_volume_uL, incubation_min_min, incubation_max_min,
                       temperature_C, max_plates_per_run, max_reagent_uL, max_iterations, max_runtime_h }
  instrument_limits: { pipettes: [{ model, min_uL, max_uL, tip_max_uL }], dead_volume_uL_by_labware, tips_available, reader_dynamic_range }
  replicates: { technical_per_point, independent_runs_to_confirm }
  acceptance_criteria: [{ id, metric: z_prime|signal_to_background|cv_control_pct|hill_slope|fit_r2|ic50_ci_fold|plateau_points_each_side|vehicle_deviation_pct,
                          operator, threshold, unit, scope: plate|compound|run, severity: technical|assay|science, source_note? }]
  failure_rules: [{ id, when: criterion_id/expression, action: tweak|rerun|flag|stop,
                    tweak: { parameter, change: set|multiply|add|extend, amount, bounds_from: parameter_range }, max_applications, priority }]
  stopping_rules: { success: all acceptance criteria met on N independent runs, max_iterations, max_consecutive_technical_failures, budget }
}

RunRecord {
  run_id, definition_hash, iteration, parent_run_id, timestamp_start/end, operator: human|ai-proposal,
  parameter_values: {name: value+unit}, plate_map, protocol_checks: {volume, tip, geometry, dead_volume results},
  raw_data_ref + hash, instrument_events, status: completed|aborted|technical_failure
}

EvaluationOutput {
  run_id, metrics: {name: value, unit, CI?}, criteria_results: [{criterion_id, value, threshold, pass}],
  fit: { model: 4PL, top, bottom, hill, ic50, ic50_ci95, r2|rmse, converged },
  classification: valid_pass|technical_fail|assay_fail|valid_negative,
  rules_fired: [{rule_id, reason}], proposed_next_run: { parameter_values, validated_against_bounds: bool, rejected_reasons[] },
  stop_decision: continue|success|stop_budget|stop_human_needed, label: PREDICTION|MEASURED|SIMULATED
}
```
Important for TFOTB: the current simulator models geometry/volume/tip only (not biology). Any biological curve it emits must be labelled SIMULATED/PREDICTION, and criteria such as Z' or IC50 can only be MEASURED when real reader data are ingested.

## Evidence gaps and conflicts
- AGM Z' >= 0.4 vs Zhang >= 0.5 vs critique of cutoffs (2.2-2.3).
- No opened source gives standard control layouts, typical working volumes per well, DMSO % rules of thumb, or dead-volume numbers for specific robots (only a Strateos snippet, UNVERIFIED).
- Cloud-lab (ECL, Strateos) protocol/audit features not opened.
- No source opened that gives actual published "failure rule" taxonomies; section 3 table is my synthesis.
- J Med Chem 2025 dose-response paper and Zhang full text not accessible; Z' vs Z distinction (Z' uses controls only) taken from AGM usage, not read in Zhang.
- No retraction/correction check performed in Crossref/PubMed (not accessible); all cited works are long-established, but status is UNVERIFIED.
- Edge-effect numbers come from one assay and two plate vendors.
