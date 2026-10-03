"""Deterministic workflow compiler + logical checks (PLAN: T21, T22).

Turns an ExperimentSpec into typed waypoints and a liquid/tip ledger. Checks are logical only:
they say nothing about real liquids, calibration or biology. Rejects rather than clips.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import jsonschema

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "experiment_spec.schema.json").read_text())
DEFAULT_Z = {"pick_tip": 15.0, "aspirate": 10.0, "dispense": 25.0, "drop_tip": 30.0}
CHECKS = (
    "spec_schema",
    "operation_order",
    "pipette_capacity",
    "source_volume",
    "tip_availability",
    "declared_bounds",
)


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def well_xy(plate: dict, well: str) -> tuple[float, float]:
    m = re.fullmatch(r"([A-H])(\d{1,2})", well)
    row, col = ord(m.group(1)) - ord("A"), int(m.group(2))
    return (
        plate["a1"]["x"] + (col - 1) * plate["pitch_mm"],
        plate["a1"]["y"] + row * plate["pitch_mm"],
    )


def _result(spec, ledger0, ledger, ops, failures):
    failed = {f["check"] for f in failures}
    return {
        "experiment_spec_hash": spec_hash(spec) if spec else None,
        "accepted": not failures,
        "operations": ops,
        "ledger_before": ledger0,
        "ledger_after": ledger,
        "checks": [
            {
                "check_name": c,
                "status": "fail" if c in failed else "pass",
                "reason": next((f["reason"] for f in failures if f["check"] == c), ""),
            }
            for c in CHECKS
        ],
        "failures": failures,
    }


def compile_spec(spec: dict) -> dict:
    try:
        jsonschema.validate(spec, SCHEMA)
    except jsonschema.ValidationError as exc:
        fail = [{"op_index": None, "check": "spec_schema", "reason": exc.message[:300]}]
        return _result(None, None, None, [], fail)

    robot, lw = spec["robot"], spec["labware"]
    wz = {**DEFAULT_Z, **lw.get("work_z_mm", {})}
    travel, cap = float(robot["travel_height_mm"]), float(robot["pipette_capacity_ul"])
    b = robot["bounds_mm"]
    ledger0 = {
        "source_ul": float(spec["inventory"]["source_volume_ul"]),
        "tips_available": int(spec["inventory"]["tips"]),
        "tip_attached": False,
        "held_ul": 0.0,
        "wells_ul": {},
    }
    led = copy.deepcopy(ledger0)
    pos = (0.0, 0.0, travel)
    ops_out, failures = [], []

    def fail(i, check, reason):
        failures.append({"op_index": i, "check": check, "reason": reason})

    for i, op in enumerate(spec["operations"]):
        kind = op["op"]
        if kind == "pick_tip":
            tgt, z = (lw["tiprack"]["x"], lw["tiprack"]["y"]), wz["pick_tip"]
            if led["tip_attached"]:
                fail(i, "operation_order", "pick_tip with a tip already attached")
            elif led["tips_available"] < 1:
                fail(i, "tip_availability", "no tips remaining")
        elif kind == "aspirate":
            tgt, z = (lw["source"]["x"], lw["source"]["y"]), wz["aspirate"]
            v = float(op["volume_ul"])
            if not led["tip_attached"]:
                fail(i, "operation_order", "aspirate without a tip")
            elif led["held_ul"] + v > cap:
                fail(i, "pipette_capacity", f"{led['held_ul'] + v} uL exceeds capacity {cap} uL")
            elif v > led["source_ul"]:
                fail(
                    i,
                    "source_volume",
                    f"requested {v} uL, only {led['source_ul']} uL left in source",
                )
        elif kind == "dispense":
            tgt, z = well_xy(lw["plate"], op["well"]), wz["dispense"]
            if not led["tip_attached"]:
                fail(i, "operation_order", "dispense without a tip")
            elif float(op["volume_ul"]) > led["held_ul"]:
                fail(i, "operation_order", "dispense volume exceeds liquid held in tip")
        else:  # drop_tip
            tgt, z = (lw["waste"]["x"], lw["waste"]["y"]), wz["drop_tip"]
            if not led["tip_attached"]:
                fail(i, "operation_order", "drop_tip without a tip")
            elif led["held_ul"] > 0:
                fail(i, "operation_order", "drop_tip while liquid remains in tip")
        if failures:
            break

        wps = []
        if pos[2] < travel:
            wps.append({"label": "raise", "x": pos[0], "y": pos[1], "z": travel})
        wps.append({"label": "travel", "x": tgt[0], "y": tgt[1], "z": travel})
        wps.append({"label": "descend", "x": tgt[0], "y": tgt[1], "z": z})
        for w in wps:
            for axis in "xyz":
                if not b[axis][0] <= w[axis] <= b[axis][1]:
                    fail(
                        i,
                        "declared_bounds",
                        f"{axis}={w[axis]} mm outside declared bounds {b[axis]}",
                    )
        if failures:
            break
        pos = (tgt[0], tgt[1], z)

        if kind == "pick_tip":
            led["tip_attached"], led["tips_available"] = True, led["tips_available"] - 1
        elif kind == "aspirate":
            led["held_ul"] += op["volume_ul"]
            led["source_ul"] -= op["volume_ul"]
        elif kind == "dispense":
            led["held_ul"] -= op["volume_ul"]
            led["wells_ul"][op["well"]] = led["wells_ul"].get(op["well"], 0.0) + op["volume_ul"]
        else:
            led["tip_attached"] = False
        ops_out.append(
            {
                "index": i,
                "op": kind,
                "args": {k: v for k, v in op.items() if k != "op"},
                "waypoints": wps,
                "ledger_after": copy.deepcopy(led),
            }
        )
    return _result(spec, ledger0, led, ops_out, failures)
