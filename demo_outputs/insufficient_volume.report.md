# Simulation report: insufficient_volume

> Workflow simulation only; not wet-lab validated

- Overall: **FAIL**
- Run: `run-54505039a04c`
- Spec hash: `0e49a82ad4e5cd143dd3c180d31b7ea0a4bb2ad3ca6aef9bc3a578ad4e7135db`
- Scene hash: `528b76b145f10a1116d5ef2f8cf448a15da4e79443a619a56c1beb15d45c13d3`
- Simulator: mujoco 3.14.0
- Review state of spec: generic_fixture_unreviewed
- Ledger before: `{"source_ul": 120.0, "tips_available": 4, "tip_attached": false, "held_ul": 0.0, "wells_ul": {}}`
- Ledger after: `{"source_ul": 20.0, "tips_available": 1, "tip_attached": true, "held_ul": 0.0, "wells_ul": {"A1": 50.0, "A2": 50.0}}`

## Checks
| check | status | reason |
|---|---|---|
| spec_schema | pass |  |
| operation_order | pass |  |
| pipette_capacity | pass |  |
| source_volume | fail | requested 50.0 uL, only 20.0 uL left in source |
| tip_availability | pass |  |
| declared_bounds | pass |  |
| joint_limits | not_modeled | skipped: workflow rejected by logical checks |
| modeled_collision | not_modeled | skipped: workflow rejected by logical checks |
| biology | not_modeled | efficacy, rescue, safety and assay outcomes are not simulated |
| physical_execution | not_modeled | no hardware, calibration or real-liquid validation |

## Failures
- op 9: **source_volume** - requested 50.0 uL, only 20.0 uL left in source

Biological outcomes are `not_modeled`. A pass here does not raise any biological claim, similarity or confidence.
