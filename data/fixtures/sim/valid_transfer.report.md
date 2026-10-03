# Simulation report: valid_transfer

> Workflow simulation only; not wet-lab validated

- Overall: **PASS**
- Run: `run-0e58a507930e`
- Spec hash: `ad9555682bf0d52fee3fd7fab3fa461aa8d7722e0774839b2d662386104a73c8`
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
| modeled_collision | pass |  |
| biology | not_modeled | efficacy, rescue, safety and assay outcomes are not simulated |
| physical_execution | not_modeled | no hardware, calibration or real-liquid validation |

## Failures
- none

Biological outcomes are `not_modeled`. A pass here does not raise any biological claim, similarity or confidence.
