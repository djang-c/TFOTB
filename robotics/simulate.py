"""MuJoCo kinematic motion check + report export (PLAN: T21-T23).

Scope: the carriage follows the compiled waypoints along straight segments; at each 1 mm sample we
query MuJoCo contacts against colliding scene geoms and test joint limits. This is a geometry check,
NOT a dynamics, calibration, liquid or biology model. Out-of-range or colliding motion is reported
as a failure and execution stops; it is never clipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import mujoco

from compile_workflow import compile_spec, spec_hash

HERE = Path(__file__).parent
SCENE = HERE / "scene.xml"
STEP_MM = 1.0
SCOPE_LABEL = "Workflow simulation only; not wet-lab validated"
APPROACH_WHITELIST: frozenset[frozenset[str]] = frozenset()  # intended contact pairs (none in v0)


def scene_hash() -> str:
    return hashlib.sha256(SCENE.read_bytes()).hexdigest()


def _segment(a, b):
    n = max(1, math.ceil(math.dist(a, b) / STEP_MM))
    for k in range(1, n + 1):
        t = k / n
        yield tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def run_motion(plan: dict) -> dict:
    model = mujoco.MjModel.from_xml_path(str(SCENE))
    data = mujoco.MjData(model)
    jr = model.jnt_range  # metres, order x,y,z
    names = lambda gid: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, gid)
    trace, events, failures, replay = [], [], [], []
    pos, steps, path_mm = (0.0, 0.0, plan["_travel"]), 0, 0.0

    def apply(p):
        data.qpos[:3] = [c / 1000.0 for c in p]
        mujoco.mj_forward(model, data)

    apply(pos)
    for op in plan["operations"]:
        status = "ok"
        for wp in op["waypoints"]:
            target = (wp["x"], wp["y"], wp["z"])
            for i, (lo, hi) in enumerate(jr[:3] * 1000.0):
                if not lo - 1e-9 <= target[i] <= hi + 1e-9:
                    failures.append(
                        {
                            "op_index": op["index"],
                            "check": "joint_limits",
                            "reason": f"axis {'xyz'[i]} target {target[i]:.1f} mm outside "
                            f"scene range [{lo:.0f}, {hi:.0f}] mm; not clipped",
                        }
                    )
                    status = "fail"
                    break
            if status == "fail":
                break
            for p in _segment(pos, target):
                apply(p)
                steps += 1
                for c in data.contact[: data.ncon]:
                    pair = frozenset((names(c.geom1), names(c.geom2)))
                    if pair not in APPROACH_WHITELIST:
                        events.append(
                            {
                                "op_index": op["index"],
                                "geoms": sorted(pair),
                                "at_mm": [round(v, 2) for v in p],
                            }
                        )
                        failures.append(
                            {
                                "op_index": op["index"],
                                "check": "modeled_collision",
                                "reason": f"unexpected contact {sorted(pair)} at "
                                f"{[round(v, 1) for v in p]} mm",
                            }
                        )
                        status = "fail"
                        break
                if status == "fail":
                    break
                if steps % 5 == 0:
                    replay.append([round(v, 2) for v in p])
            if status == "fail":
                break
            path_mm += math.dist(pos, target)
            pos = target
        trace.append(
            {
                "op_index": op["index"],
                "op": op["op"],
                "status": status,
                "end_mm": [round(v, 2) for v in pos],
            }
        )
        if status == "fail":
            break
    return {
        "trace": trace,
        "events": events,
        "failures": failures,
        "steps": steps,
        "path_mm": round(path_mm, 2),
        "replay_points_mm": replay,
    }


def run(spec_path: Path, out_dir: Path, seed: int = 0) -> dict:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    spec = json.loads(Path(spec_path).read_text())
    plan = compile_spec(spec)
    checks = list(plan["checks"])
    failures = list(plan["failures"])
    motion = {
        "trace": [],
        "events": [],
        "failures": [],
        "steps": 0,
        "path_mm": 0.0,
        "replay_points_mm": [],
    }

    if plan["accepted"]:
        plan["_travel"] = float(spec["robot"]["travel_height_mm"])
        motion = run_motion(plan)
        failures += motion["failures"]
        bad = {f["check"]: f["reason"] for f in motion["failures"]}
        for name in ("joint_limits", "modeled_collision"):
            checks.append(
                {
                    "check_name": name,
                    "status": "fail" if name in bad else "pass",
                    "reason": bad.get(name, ""),
                }
            )
    else:
        for name in ("joint_limits", "modeled_collision"):
            checks.append(
                {
                    "check_name": name,
                    "status": "not_modeled",
                    "reason": "skipped: workflow rejected by logical checks",
                }
            )
    checks.append(
        {
            "check_name": "biology",
            "status": "not_modeled",
            "reason": "efficacy, rescue, safety and assay outcomes are not simulated",
        }
    )
    checks.append(
        {
            "check_name": "physical_execution",
            "status": "not_modeled",
            "reason": "no hardware, calibration or real-liquid validation",
        }
    )

    overall = "pass" if not failures else "fail"
    report = {
        "run_id": "run-" + hashlib.sha256(
            f"{spec_hash(spec)}|{seed}|{scene_hash()}|mujoco {mujoco.__version__}|adapter 0.1.0".encode()
        ).hexdigest()[:12],
        "experiment_spec_hash": plan["experiment_spec_hash"] or spec_hash(spec),
        "scene_hash": scene_hash(),
        "simulator_name": "mujoco",
        "simulator_version": mujoco.__version__,
        "adapter_version": "0.1.0",
        "random_seed": seed,
        "review_state": spec.get("proposal_ref", {}).get("review_state", "unknown"),
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "operation_trace": motion["trace"],
        "ledger_before": plan["ledger_before"],
        "ledger_after": plan["ledger_after"],
        "checks": checks,
        "modeled_collision_events": motion["events"],
        "failures": failures,
        "simulation_steps": motion["steps"],
        "path_length_mm": motion["path_mm"],
        "simulation_time_note": "kinematic samples at 1 mm; not physical time",
        "wall_clock_time_s": round(time.perf_counter() - t0, 4),
        "scope_label": SCOPE_LABEL,
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(spec_path).stem
    (out_dir / f"{stem}.report.json").write_text(json.dumps(report, indent=2))
    (out_dir / f"{stem}.trajectory.json").write_text(
        json.dumps(
            {"scope_label": SCOPE_LABEL, "units": "mm", "points": motion["replay_points_mm"]}
        )
    )
    (out_dir / f"{stem}.report.md").write_text(render_md(report, stem))
    return report


def render_md(r: dict, stem: str) -> str:
    rows = "\n".join(f"| {c['check_name']} | {c['status']} | {c['reason']} |" for c in r["checks"])
    fails = (
        "\n".join(f"- op {f['op_index']}: **{f['check']}** - {f['reason']}" for f in r["failures"])
        or "- none"
    )
    return (
        f"# Simulation report: {stem}\n\n> {r['scope_label']}\n\n"
        f"- Overall: **{r['overall'].upper()}**\n- Run: `{r['run_id']}`\n"
        f"- Spec hash: `{r['experiment_spec_hash']}`\n- Scene hash: `{r['scene_hash']}`\n"
        f"- Simulator: {r['simulator_name']} {r['simulator_version']}\n"
        f"- Review state of spec: {r['review_state']}\n"
        f"- Ledger before: `{json.dumps(r['ledger_before'])}`\n"
        f"- Ledger after: `{json.dumps(r['ledger_after'])}`\n\n"
        f"## Checks\n| check | status | reason |\n|---|---|---|\n{rows}\n\n## Failures\n{fails}\n\n"
        "Biological outcomes are `not_modeled`. A pass here does not raise any biological claim, "
        "similarity or confidence.\n"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", default=str(HERE.parent / "demo_outputs"))
    ap.add_argument(
        "--seed",
        type=int,
        default=0,
        help="recorded in the report; the kinematic check is deterministic",
    )
    args = ap.parse_args()
    try:
        raw = json.loads(Path(args.spec).read_text())
    except OSError as exc:
        raise SystemExit(f"cannot read {args.spec}: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{args.spec} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"{args.spec} must contain a JSON object (an experiment specification)")
    rep = run(Path(args.spec), Path(args.out), args.seed)
    print(rep["overall"], [f["check"] for f in rep["failures"]])
