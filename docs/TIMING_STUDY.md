# Timing study: the people side of the 10× case

The 10× case compares the typical way with TFOTB. The TFOTB side is measured (`scripts/measure_journey.py`, results in
`docs/measurements/journey.json`): five calls, median 2.5 s on the live app, and a fixed checklist of 7 items that all pass.
**The typical-way side has not been measured on people.** This protocol measures it. Nobody has run it yet; until someone
does, the 10× figures on `/10x` stay a model.

## What is measured
Time to answer one of Maria's questions about CLN3 disease to a fixed quality bar, once without TFOTB and once with it.
Tasks are cut down so each fits in a session (the full journey takes days by hand, so it cannot be timed in one sitting).

| Step id | Task (CLN3 disease) | Done when |
|---|---|---|
| `m1` | Which other diseases share a mechanism, gene or symptoms with CLN3 disease, and why? | At least 3 diseases listed, each with its reason and a source |
| `m2` | Which patient groups and registries exist for CLN3 disease, and is there a registered study? | At least 2 groups with links, plus 1 study or registry with a link |
| `m3` | Name 2 researchers who work on the mechanism CLN3 shares with another disease, with an affiliation | 2 named researchers, each with a paper |
| `m4` | A half-page evidence brief for a partner: the connection, its sources, what is unknown | Every statement cites a source; a checker can open each one |

## Participants and conditions
- 3 to 5 people with no prior use of TFOTB. Record each person's background (patient-group volunteer, student, scientist). Do not use the builders.
- Each person does each step **twice**, in counterbalanced order: with the usual tools (search engines, PubMed, ClinicalTrials.gov, GARD, the person's own habits) and with TFOTB at the live URL. Use a different disease for the second run (CLN3 and Niemann-Pick type C) so the first run does not teach the second.
- Cap each task at 90 minutes. A capped, incomplete task is recorded as failed and **not** counted in the ratio.
- Time with a stopwatch from reading the task to saying "done". Do not count setup or explanation.

## Quality bar (same for both conditions)
A second person checks the "Done when" column without knowing which condition produced the answer. Record pass or fail. Only pairs where both runs pass enter the ratio.

## Recording
Fill `frontend/public/measurements/timing-results.json` (format below). The `/10x` page reads it and shows, per step, n, the median times and the median ratio. Report everything, including a ratio under 10×.

```json
{
  "run_on": "2026-10-05",
  "participants": [
    {"id": "P1", "role": "graduate student",
     "steps": {"m1": {"manualMin": 55, "tfotbMin": 9, "manualPass": true, "tfotbPass": true}}}
  ]
}
```

## What to report
n per step; median and range of both times; the median ratio and its range; how many pairs failed the bar and why; participants' backgrounds; that setup time and who chose the tasks are disclosed. With n this small the ratio is an indication, not a population estimate.
