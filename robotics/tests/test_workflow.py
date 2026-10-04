import copy
import json
from pathlib import Path

import pytest

from compile_workflow import compile_spec
from simulate import SCOPE_LABEL, run

FIX = Path(__file__).parent.parent / "fixtures"
load = lambda n: json.loads((FIX / f"{n}.json").read_text())


def checks(rep):
    return {c["check_name"]: c["status"] for c in rep["checks"]}


def test_valid_transfer_passes_and_ledger_balances(tmp_path):
    rep = run(FIX / "valid_transfer.json", tmp_path)
    assert rep["overall"] == "pass" and not rep["failures"]
    la = rep["ledger_after"]
    assert la["source_ul"] == 850 and la["tips_available"] == 1 and la["held_ul"] == 0
    assert la["wells_ul"] == {"A1": 50, "A2": 50, "A3": 50} and not la["tip_attached"]


@pytest.mark.parametrize(
    "name,check",
    [
        ("insufficient_volume", "source_volume"),
        ("no_tips", "tip_availability"),
        ("blocked_path", "modeled_collision"),
        ("out_of_range", "joint_limits"),
    ],
)
def test_failure_fixtures_are_rejected_with_explicit_reason(tmp_path, name, check):
    rep = run(FIX / f"{name}.json", tmp_path)
    assert rep["overall"] == "fail"
    assert [f["check"] for f in rep["failures"]] == [check]
    assert rep["failures"][0]["reason"]
    assert checks(rep)[check] == "fail"


def test_logical_rejection_skips_motion_and_says_so(tmp_path):
    rep = run(FIX / "insufficient_volume.json", tmp_path)
    assert checks(rep)["modeled_collision"] == "not_modeled" and rep["operation_trace"] == []


def test_out_of_range_is_failed_not_clipped(tmp_path):
    rep = run(FIX / "out_of_range.json", tmp_path)
    assert rep["operation_trace"][-1]["status"] == "fail"
    assert all(t["end_mm"][1] <= 200 for t in rep["operation_trace"])


def test_biology_and_hardware_always_not_modeled(tmp_path):
    for name in ("valid_transfer", "blocked_path"):
        rep = run(FIX / f"{name}.json", tmp_path)
        assert (
            checks(rep)["biology"] == "not_modeled"
            and checks(rep)["physical_execution"] == "not_modeled"
        )
        assert rep["scope_label"] == SCOPE_LABEL


def test_rerun_is_reproducible(tmp_path):
    a, b = (run(FIX / "valid_transfer.json", tmp_path / n) for n in "ab")
    volatile = {"started_at", "finished_at", "wall_clock_time_s"}
    assert {k: v for k, v in a.items() if k not in volatile} == {
        k: v for k, v in b.items() if k not in volatile
    }


def test_report_contains_hashes_and_versions(tmp_path):
    rep = run(FIX / "valid_transfer.json", tmp_path)
    for k in (
        "experiment_spec_hash",
        "scene_hash",
        "simulator_version",
        "random_seed",
        "review_state",
    ):
        assert rep[k] not in (None, "")


def test_schema_violation_is_rejected():
    bad = copy.deepcopy(load("valid_transfer"))
    bad["operations"][2]["well"] = "Z99"
    out = compile_spec(bad)
    assert not out["accepted"] and out["failures"][0]["check"] == "spec_schema"


def test_dispense_more_than_held_is_rejected():
    s = load("valid_transfer")
    s["operations"][2]["volume_ul"] = 80
    assert compile_spec(s)["failures"][0]["check"] == "operation_order"


def test_pipette_capacity_enforced():
    s = load("valid_transfer")
    s["operations"][1]["volume_ul"] = 250
    assert compile_spec(s)["failures"][0]["check"] == "pipette_capacity"


def test_float_split_dispense_is_not_rejected_by_round_off():
    """0.1 + 0.2 uL dispensed from a 0.3 uL aspirate is a valid split (binary float round-off)."""
    spec = load("valid_transfer")
    spec["operations"] = [
        {"op": "pick_tip"},
        {"op": "aspirate", "volume_ul": 0.3},
        {"op": "dispense", "well": "A1", "volume_ul": 0.1},
        {"op": "dispense", "well": "A2", "volume_ul": 0.2},
        {"op": "drop_tip"},
    ]
    out = compile_spec(spec)
    assert not out["failures"], out["failures"]


def test_real_volume_overdraw_still_fails_with_tolerance():
    spec = load("valid_transfer")
    spec["operations"] = [
        {"op": "pick_tip"},
        {"op": "aspirate", "volume_ul": 0.3},
        {"op": "dispense", "well": "A1", "volume_ul": 0.31},
    ]
    assert [f["check"] for f in compile_spec(spec)["failures"]] == ["operation_order"]


def test_run_id_depends_on_seed_and_is_stable_for_the_same_inputs(tmp_path):
    a = run(FIX / "valid_transfer.json", tmp_path / "a")
    b = run(FIX / "valid_transfer.json", tmp_path / "b")
    c = run(FIX / "valid_transfer.json", tmp_path / "c", seed=1)
    assert a["run_id"] == b["run_id"] != c["run_id"]


def test_the_command_line_gives_a_plain_message_for_a_missing_file_bad_json_or_a_non_object(tmp_path):
    import subprocess
    import sys

    script = Path(__file__).parent.parent / "simulate.py"
    bad_json, not_obj = tmp_path / "bad.json", tmp_path / "list.json"
    bad_json.write_text("{nope")
    not_obj.write_text("[1]")
    for spec, words in (("/does/not/exist.json", "cannot read"), (str(bad_json), "not valid JSON"), (str(not_obj), "JSON object")):
        p = subprocess.run([sys.executable, str(script), spec, "--out", str(tmp_path)], capture_output=True, text=True, check=False)
        assert p.returncode != 0 and words in p.stderr and "Traceback" not in p.stderr
