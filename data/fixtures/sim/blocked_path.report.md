# Simulation report: blocked_path

> Workflow simulation only; not wet-lab validated

- Overall: **FAIL**
- Run: `run-de7f1eeecd5d`
- Spec hash: `d1ea033b5608b33e90132aedfe3fb38d8cd2b5cf22c7a368bffd1e552e479b7d`
- Scene hash: `528b76b145f10a1116d5ef2f8cf448a15da4e79443a619a56c1beb15d45c13d3`
- Simulator: mujoco 3.14.0
- Review state of spec: generic_fixture_unreviewed
- Ledger before: `{"source_ul": 1000.0, "tips_available": 4, "tip_attached": false, "held_ul": 0.0, "wells_ul": {}}`
- Ledger after: `{"source_ul": 850.0, "tips_available": 1, "tip_attached": false, "held_ul": 0.0, "wells_ul": {"A1": 50.0, "A2": 50.0, "A3": 50.0}}`

## Checks
| check | status | reason |
|---|---|---|
| spec_schema | pass |  |
| operation_order | pass |  |
| pipette_capacity | pass |  |
| source_volume | pass |  |
| tip_availability | pass |  |
| declared_bounds | pass |  |
| joint_limits | pass |  |
| modeled_collision | fail | unexpected contact ['pipette', 'tower'] at [89.2, 109.7, 20.0] mm |
| biology | not_modeled | efficacy, rescue, safety and assay outcomes are not simulated |
| physical_execution | not_modeled | no hardware, calibration or real-liquid validation |

## Failures
- op 2: **modeled_collision** - unexpected contact ['pipette', 'tower'] at [89.2, 109.7, 20.0] mm

Biological outcomes are `not_modeled`. A pass here does not raise any biological claim, similarity or confidence.
