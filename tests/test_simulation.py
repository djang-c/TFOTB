"""T23 tests. Reports are produced by the real simulator on the generic fixtures; claims are SYNTHETIC."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.conftest import make_claim

from atlas.channels.base import ChannelRegistry
from atlas.channels.claims import build_claim_channels
from atlas.connections import run_query
from atlas.simulation import SimulationError, SimulationRun, link_claim, run_from_report
from atlas.store import PublicStore

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parent.parent
Q, A = "MONDO:0000001", "MONDO:0000002"


def report(**kw):
    base = {
        "run_id": "run-abc123", "experiment_spec_hash": "a" * 64, "scene_hash": "b" * 64, "simulator_name": "mujoco",
        "simulator_version": "3.14.0", "adapter_version": "0.1.0", "random_seed": 0,
        "review_state": "generic_fixture_unreviewed", "overall": "pass", "failures": [],
        "scope_label": "Workflow simulation only; not wet-lab validated", "simulation_steps": 10, "path_length_mm": 5.0,
        "checks": [
            {"check_name": "joint_limits", "status": "pass", "reason": ""},
            {"check_name": "biology", "status": "not_modeled", "reason": "not simulated"},
            {"check_name": "physical_execution", "status": "not_modeled", "reason": "no hardware"},
        ],
    }
    return {**base, **kw}


def test_run_exposes_spec_hash_model_version_review_state_and_source_claims():
    run = run_from_report(report(), ("CLAIM:q",))
    assert run.run_id == "SIM:run-abc123" and run.experiment_spec_hash == "a" * 64
    assert run.simulator_version == "3.14.0" and run.spec_review_state == "generic_fixture_unreviewed"
    assert run.source_claim_ids == ("CLAIM:q",) and run.biology == "not_modeled" and run.physical_validation == "absent"


def test_a_run_that_does_not_mark_biology_not_modelled_cannot_exist():
    bad = report(checks=[{"check_name": "biology", "status": "pass", "reason": ""}])
    with pytest.raises(ValueError, match="not_modeled"):
        run_from_report(bad)
    with pytest.raises(SimulationError, match="missing"):
        run_from_report({"run_id": "x"})


def test_a_pass_with_recorded_failures_or_without_the_scope_label_is_rejected():
    fail = [{"op_index": 1, "check": "modeled_collision", "reason": "x"}]
    with pytest.raises(ValueError, match="failures"):
        run_from_report(report(failures=fail))
    with pytest.raises(ValueError, match="wet-lab"):
        run_from_report(report(scope_label="Simulation"))


def test_failed_runs_are_recorded_as_failed_with_their_reasons():
    fail = [{"op_index": 1, "check": "modeled_collision", "reason": "unexpected contact"}]
    run = run_from_report(report(overall="fail", failures=fail))
    assert run.overall == "fail" and run.failures[0]["reason"] == "unexpected contact"


def test_link_claim_is_a_labelled_unreviewed_prediction_traceable_to_its_sources():
    store = PublicStore()
    store.add(make_claim("CLAIM:q", "ACCUMULATES_IN_COMPARTMENT", subject_id=Q, object_id="GO:0005764"))
    run = run_from_report(report(), ("CLAIM:q",))
    c = link_claim(run, Q, store.claims)
    assert c.predicate == "SIMULATES_WORKFLOW_FOR" and c.subject_id == run.run_id and c.object_id == Q
    assert c.status.value == "computational_prediction" and c.review_state.value == "unreviewed"
    assert c.derived_from == ("CLAIM:q",) and "not wet-lab validated" in c.source_span
    with pytest.raises(SimulationError, match="not in the store"):
        link_claim(run_from_report(report(), ("CLAIM:nope",)), Q, store.claims)


def test_a_passing_simulation_changes_no_ranking_or_category():
    def outcome(store):
        reg = ChannelRegistry()
        for ch in build_claim_channels(store):
            reg.register(ch)
        return run_query(Q, reg, store.claims, dataset_version="t", per_source=[], now=NOW)

    store = PublicStore()
    for cid, d in (("CLAIM:q", Q), ("CLAIM:a", A)):
        store.add(make_claim(cid, "ACCUMULATES_IN_COMPARTMENT", subject_id=d, object_id="GO:0005764", lineage=f"STUDY:{cid}"))
    before = [(r.result.candidate_id, r.result.category) for r in outcome(store).ranked]
    run = run_from_report(report(), ("CLAIM:q",))
    store.add(link_claim(run, Q, store.claims))
    store.add(link_claim(run, A, store.claims))
    after = [(r.result.candidate_id, r.result.category) for r in outcome(store).ranked]
    assert before == after


def test_run_built_from_a_real_simulator_report_when_the_demo_outputs_exist():
    path = next(iter((ROOT / "demo_outputs").glob("valid_transfer.report.json")), None)
    if path is None:
        pytest.skip("run robotics/simulate.py first")
    run = run_from_report(json.loads(path.read_text()))
    assert isinstance(run, SimulationRun) and run.overall == "pass"
