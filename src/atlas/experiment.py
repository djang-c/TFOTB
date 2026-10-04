"""Closed-loop experiments: the researcher defines the experiment, the robot plan is checked against real limits,
results are evaluated against the researcher's criteria, and the next run changes only what the researcher allowed.

Grounding: docs/research/closed_loop_experiments.md (NIH Assay Guidance Manual plate acceptance, Z'-factor of
Zhang 1999, 4-parameter logistic dose-response and the bend-point rule of Sebaugh 2011, Opentrons pipette ranges).
The rule types and the default rules are a DESIGN proposal, not a published prescription; every default is shown
to the researcher and can be changed.

What is real here and what is not:
- The definition (parameters, units, ranges, constraints, criteria, rules) is the researcher's.
- The robot plan uses real arithmetic on volumes, concentrations, DMSO and tips, and the MuJoCo motion check of the
  pipetting robot (robotics/). It is a plan check, not a wet-lab run.
- Readings come either from the researcher's plate reader (MEASURED) or from `synthetic_readings` (SYNTHETIC: a
  stated 4PL model with noise and an edge effect, for showing the loop; never evidence about any compound).
- Evaluation is arithmetic (Z', CV, S/B, a 4PL fit). The next run is chosen by the researcher's rules; an AI model
  may only order and explain the changes the rules allow (`ai_review`), and its choice is re-checked against the
  bounds. Nothing outside the researcher's ranges is ever run, and nothing is clipped to fit.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROWS = "ABCDEFGH"
BEND_K = 4.6805  # Sebaugh & McCray: 4PL bend points at IC50 * K**(+-1/hill)
EDGE_LOSS = 0.35  # synthetic model only: outer wells read ~35% lower (Mansoury 2021, one assay, unwrapped plates)


# ---- the researcher's definition ---------------------------------------------------------------------------------

class Parameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    label: str
    unit: str
    role: Literal["varied", "fixed"] = "varied"
    value: float
    min: float
    max: float
    max_change_factor: float | None = Field(default=None, gt=1, description="largest x-fold change in one run")

    @model_validator(mode="after")
    def _in_range(self) -> Parameter:
        if not self.min <= self.value <= self.max:
            raise ValueError(f"{self.name}: value {self.value} is outside its range [{self.min}, {self.max}]")
        return self


class Instrument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipette: str = "P20 single-channel"
    pipette_min_ul: float = 1.0
    pipette_max_ul: float = 20.0
    tips_available: int = 96
    well_max_ul: float = 300.0  # 96-well plate working maximum, set by the researcher for their plate


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    metric: Literal["z_prime", "signal_to_background", "cv_vehicle_pct", "cv_positive_pct", "fit_r2",
                    "points_low_plateau", "points_high_plateau", "ic50_inside_range"]
    op: Literal[">=", "<="]
    threshold: float
    severity: Literal["technical", "assay"] = "technical"
    why: str = ""


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    when: str  # a criterion id, or a plan check name (e.g. "dmso_limit")
    action: Literal["change", "rerun", "stop"]
    parameter: str | None = None
    operation: Literal["multiply", "add", "set"] | None = None
    amount: float | None = None
    max_uses: int = 2
    why: str = ""


class Definition(BaseModel):
    """One experiment as the researcher defines it. Units are part of every parameter."""
    model_config = ConfigDict(extra="forbid")
    title: str
    assay: Literal["dose_response"] = "dose_response"
    readout: Literal["luminescence", "fluorescence", "absorbance"] = "luminescence"
    hypothesis: str = ""
    expected: str = ""
    parameters: list[Parameter]
    instrument: Instrument = Instrument()
    edge_policy: Literal["buffer_outer_wells", "use_all_wells"] = "buffer_outer_wells"
    controls_per_type: int = Field(default=6, ge=3, le=8)
    criteria: list[Criterion]
    rules: list[Rule]
    passes_needed: int = Field(default=2, ge=1, le=5, description="independent passing runs before a result counts")
    max_runs: int = Field(default=6, ge=1, le=20)

    @model_validator(mode="after")
    def _consistent(self) -> Definition:
        names = {p.name for p in self.parameters}
        missing = {"top_concentration_um", "dilution_factor", "n_concentrations", "replicates", "final_volume_ul",
                   "transfer_volume_ul", "stock_concentration_um", "dmso_max_pct", "incubation_h"} - names
        if missing:
            raise ValueError(f"a dose-response definition needs the parameters: {sorted(missing)}")
        crit = {c.id for c in self.criteria} | set(PLAN_CHECKS)
        for r in self.rules:
            if r.when not in crit:
                raise ValueError(f"rule {r.id}: '{r.when}' is not a criterion or a plan check")
            if r.action == "change":
                if r.parameter not in names or r.operation is None or r.amount is None:
                    raise ValueError(f"rule {r.id}: a change needs a known parameter, an operation and an amount")
                if next(p for p in self.parameters if p.name == r.parameter).role == "fixed":
                    raise ValueError(f"rule {r.id}: {r.parameter} is fixed by the researcher and cannot be changed")
        return self

    def values(self) -> dict[str, float]:
        return {p.name: p.value for p in self.parameters}

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]


# ---- the robot plan ----------------------------------------------------------------------------------------------

PLAN_CHECKS = ("plate_capacity", "pipette_range", "stock_limit", "dmso_limit", "well_volume", "tips", "motion")


def _concentrations(v: dict[str, float]) -> list[float]:
    n, top, d = int(v["n_concentrations"]), v["top_concentration_um"], v["dilution_factor"]
    return [top / d**i for i in range(n)]


def layout(defn: Definition, v: dict[str, float]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Plate map: vehicle (0% effect) and positive (full effect) controls, then concentrations x replicates.
    With buffer_outer_wells the outer ring holds buffer only (it reads differently: edge effect)."""
    problems = []
    buffered = defn.edge_policy == "buffer_outer_wells"
    rows = ROWS[1:7] if buffered else ROWS
    cols = list(range(2, 12)) if buffered else list(range(1, 13))
    wells: dict[str, dict[str, Any]] = {}
    if buffered:
        for r in ROWS:
            for c in range(1, 13):
                if r in "AH" or c in (1, 12):
                    wells[f"{r}{c}"] = {"role": "buffer"}
    n, reps, k = int(v["n_concentrations"]), int(v["replicates"]), defn.controls_per_type
    if k > len(rows):
        problems.append(f"{k} controls of each type need {k} rows; the usable plate has {len(rows)}")
    if n > len(cols) - 2:
        problems.append(f"{n} concentrations need {n} columns; {len(cols) - 2} are free after the two control columns")
    if reps > len(rows):
        problems.append(f"{reps} replicates need {reps} rows; the usable plate has {len(rows)}")
    if problems:
        return wells, problems
    for i, r in enumerate(rows[:k]):
        wells[f"{r}{cols[0]}"] = {"role": "vehicle"}
        wells[f"{r}{cols[-1]}"] = {"role": "positive"}
    for j, conc in enumerate(_concentrations(v)):
        for r in rows[:reps]:
            wells[f"{r}{cols[1 + j]}"] = {"role": "sample", "conc_um": conc, "index": j}
    return wells, []


def plan(defn: Definition, v: dict[str, float] | None = None, *, motion: bool = True) -> dict[str, Any]:
    """What the robot would do, and whether it can: every check uses the researcher's numbers and units."""
    v = v or defn.values()
    ins = defn.instrument
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "pass" if ok else "fail", "detail": detail})

    wells, problems = layout(defn, v)
    check("plate_capacity", not problems, "; ".join(problems) or "the layout fits a 96-well plate")
    t, final, stock = v["transfer_volume_ul"], v["final_volume_ul"], v["stock_concentration_um"]
    check("pipette_range", ins.pipette_min_ul <= t <= ins.pipette_max_ul,
          f"each compound transfer is {t:g} uL; the {ins.pipette} handles {ins.pipette_min_ul:g}-{ins.pipette_max_ul:g} uL")
    tube_top = v["top_concentration_um"] * final / t  # the top tube of the dilution series (in DMSO)
    check("stock_limit", tube_top <= stock,
          f"the top dilution tube must be {tube_top:,.0f} uM for {v['top_concentration_um']:g} uM in the well; "
          f"the stock is {stock:,.0f} uM")
    dmso = 100 * t / final
    check("dmso_limit", dmso <= v["dmso_max_pct"],
          f"final DMSO is {dmso:.2f}% ({t:g} uL in {final:g} uL); the limit is {v['dmso_max_pct']:g}%")
    check("well_volume", final <= ins.well_max_ul, f"{final:g} uL per well; the plate holds {ins.well_max_ul:g} uL")
    n_tips = int(v["n_concentrations"]) + 2  # one tip per concentration and per control type (DESIGN)
    check("tips", n_tips <= ins.tips_available, f"{n_tips} tips needed; {ins.tips_available} available")
    ops = []
    if not problems:
        for group in ([w for w, x in wells.items() if x["role"] == "vehicle"],
                      [w for w, x in wells.items() if x["role"] == "positive"],
                      *[[w for w, x in wells.items() if x.get("index") == j] for j in range(int(v["n_concentrations"]))]):
            ops.append({"op": "pick_tip"})
            ops.append({"op": "aspirate", "volume_ul": round(t * len(group), 3)})
            ops += [{"op": "dispense", "well": w, "volume_ul": t} for w in sorted(group)]
            ops.append({"op": "drop_tip"})
    robot = None
    if motion and ops and all(c["status"] == "pass" for c in checks):
        robot = motion_check(ops, ins, n_tips)
        check("motion", robot["overall"] == "pass", "; ".join(f["reason"] for f in robot["failures"][:2])
              or f"MuJoCo geometry check passed over {robot['path_length_mm']:,.0f} mm of travel")
    else:
        checks.append({"check": "motion", "status": "not_run", "detail": "skipped: an earlier check failed" if ops else
                       "skipped: no plate layout"})
    concs = _concentrations(v)
    return {
        "values": v, "wells": wells, "concentrations_um": concs, "operations": len(ops), "ops": ops, "tips": n_tips,
        "dilution_series": {"top_tube_um": tube_top, "factor": v["dilution_factor"], "steps": int(v["n_concentrations"])},
        "checks": checks, "feasible": all(c["status"] in ("pass", "not_run") for c in checks) and not problems
        and all(c["status"] != "fail" for c in checks),
        "robot": robot,
        "scope": "Plan check only: arithmetic on the researcher's volumes and the MuJoCo geometry of the robot. "
                 "Liquids, calibration and biology are not modelled. The scene has one reservoir position, so every "
                 "aspiration is drawn there in the motion check.",
    }


def motion_check(ops: list[dict[str, Any]], ins: Instrument, tips: int) -> dict[str, Any]:
    """Runs the pipetting robot's MuJoCo motion check (robotics/simulate.py) on the planned operations."""
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parents[2] / "robotics"
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    from compile_workflow import compile_spec  # type: ignore[import-not-found]
    from simulate import run_motion  # type: ignore[import-not-found]

    spec = json.loads((here / "fixtures" / "valid_transfer.json").read_text())  # the scene's robot and labware
    spec["robot"]["pipette_capacity_ul"] = ins.pipette_max_ul
    spec["inventory"] = {"source_volume_ul": 1e6, "tips": tips}
    spec["proposal_ref"]["proposal_id"] = "CLOSED-LOOP-PLAN"
    spec["operations"] = ops
    compiled = compile_spec(spec)
    fails = list(compiled["failures"])
    out: dict[str, Any] = {"path_length_mm": 0.0, "steps": 0, "replay_points_mm": []}
    if compiled["accepted"]:
        compiled["_travel"] = float(spec["robot"]["travel_height_mm"])
        m = run_motion(compiled)
        fails += m["failures"]
        out = {"path_length_mm": m["path_mm"], "steps": m["steps"], "replay_points_mm": m["replay_points_mm"][::4]}
    return {"overall": "fail" if fails else "pass", "failures": fails, **out}


# ---- readings ----------------------------------------------------------------------------------------------------

def synthetic_readings(defn: Definition, p: dict[str, Any], *, seed: int = 0, ic50_um: float = 0.8, hill: float = 1.0,
                       ) -> dict[str, Any]:
    """SYNTHETIC plate-reader values for showing the loop: a 4PL curve (stated true IC50 and Hill slope), a signal
    window that grows with incubation (half of it at 6 h), 5% noise, and ~35% lower reads in outer wells.
    Not data about any compound, and never stored as evidence."""
    rng = random.Random(seed)
    inc = p["values"]["incubation_h"]
    window = 1 - math.exp(-inc / 8.66)  # 50% at 6 h (DESIGN of the synthetic model)
    high, low = 2000 + 60000 * window, 2000.0
    out = {}
    for w, x in p["wells"].items():
        if x["role"] == "buffer":
            continue
        frac = {"vehicle": 1.0, "positive": 0.0}.get(x["role"])
        if frac is None:
            frac = 1 / (1 + (x["conc_um"] / ic50_um) ** hill)
        val = low + (high - low) * frac
        if w[0] in "AH" or w[1:] in ("1", "12"):
            val *= 1 - EDGE_LOSS
        out[w] = max(0.0, val * (1 + rng.gauss(0, 0.05)) + rng.gauss(0, 300))
    return {"label": "SYNTHETIC", "readings": out,
            "model": f"4PL with IC50 {ic50_um} uM and Hill slope {hill}; signal window 1-exp(-t/8.66 h); 5% "
                     f"proportional and 300-count additive noise; outer wells -{EDGE_LOSS:.0%}; seed {seed}"}


# ---- evaluation --------------------------------------------------------------------------------------------------

def _fit_4pl(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Least-squares 4PL on log10 concentration (Levenberg-Marquardt). y = activity in % of vehicle."""
    lx = np.log10(x)
    p = np.array([float(y.min()), float(y.max()), float(np.median(lx)), 1.0])  # bottom, top, log IC50, hill

    def f(q: np.ndarray) -> np.ndarray:
        return q[0] + (q[1] - q[0]) / (1 + 10 ** np.clip((lx - q[2]) * q[3], -50, 50))

    lam = 1e-2
    for _ in range(200):
        r = y - f(p)
        jac = np.empty((len(x), 4))
        for i in range(4):
            d = np.zeros(4)
            d[i] = 1e-6 * max(1.0, abs(p[i]))
            jac[:, i] = (f(p + d) - f(p - d)) / (2 * d[i])
        a = jac.T @ jac
        step = np.linalg.solve(a + lam * np.diag(np.diag(a) + 1e-12), jac.T @ r)
        if np.sum((y - f(p + step)) ** 2) < np.sum(r**2):
            p, lam = p + step, lam / 3
            if np.max(np.abs(step)) < 1e-8:
                break
        else:
            lam *= 4
    res = y - f(p)
    ss = float(np.sum((y - y.mean()) ** 2))
    return {"bottom": float(p[0]), "top": float(p[1]), "ic50_um": float(10 ** p[2]), "hill": float(p[3]),
            "r2": 1 - float(np.sum(res**2)) / ss if ss > 0 else 0.0}


def evaluate(defn: Definition, p: dict[str, Any], readings: dict[str, float]) -> dict[str, Any]:
    """Every number the researcher's criteria use, then pass or fail for each criterion."""
    roles = p["wells"]

    def vals(role: str) -> np.ndarray:
        return np.array([readings[w] for w, x in roles.items() if x["role"] == role and w in readings], float)

    veh, pos = vals("vehicle"), vals("positive")
    m: dict[str, float | None] = dict.fromkeys(
        ("z_prime", "signal_to_background", "cv_vehicle_pct", "cv_positive_pct", "fit_r2",
         "points_low_plateau", "points_high_plateau", "ic50_inside_range"))
    fit = None
    if len(veh) >= 2 and len(pos) >= 2:
        mv, mp = float(veh.mean()), float(pos.mean())
        sv, sp = float(veh.std(ddof=1)), float(pos.std(ddof=1))
        m["z_prime"] = 1 - 3 * (sv + sp) / abs(mv - mp) if mv != mp else None
        m["signal_to_background"] = mv / mp if mp > 0 else None
        m["cv_vehicle_pct"] = 100 * sv / mv if mv else None
        m["cv_positive_pct"] = 100 * sp / mp if mp else None
        pts = [(x["conc_um"], 100 * (readings[w] - mp) / (mv - mp)) for w, x in roles.items()
               if x["role"] == "sample" and w in readings and mv != mp]
        if len({c for c, _ in pts}) >= 4:
            fit = _fit_4pl(np.array([c for c, _ in pts]), np.array([a for _, a in pts]))
            lo_bend = fit["ic50_um"] / BEND_K ** (1 / abs(fit["hill"])) if fit["hill"] else 0
            hi_bend = fit["ic50_um"] * BEND_K ** (1 / abs(fit["hill"])) if fit["hill"] else math.inf
            concs = p["concentrations_um"]
            m["fit_r2"] = fit["r2"]
            m["points_low_plateau"] = float(sum(c <= lo_bend for c in concs))
            m["points_high_plateau"] = float(sum(c >= hi_bend for c in concs))
            m["ic50_inside_range"] = float(min(concs) <= fit["ic50_um"] <= max(concs))
    results = []
    for c in defn.criteria:
        val = m[c.metric]
        ok = val is not None and (val >= c.threshold if c.op == ">=" else val <= c.threshold)
        results.append({"id": c.id, "metric": c.metric, "value": val, "op": c.op, "threshold": c.threshold,
                        "severity": c.severity, "pass": ok, "why": c.why})
    tech = [r for r in results if not r["pass"] and r["severity"] == "technical"]
    assay = [r for r in results if not r["pass"] and r["severity"] == "assay"]
    verdict = "technical_fail" if tech else "assay_fail" if assay else "pass"
    return {"metrics": m, "fit": fit, "criteria": results, "verdict": verdict}


# ---- the next run ------------------------------------------------------------------------------------------------

def _apply(rule: Rule, old: float) -> float:
    assert rule.amount is not None
    return {"multiply": old * rule.amount, "add": old + rule.amount, "set": rule.amount}[rule.operation or "set"]


def candidates(defn: Definition, failed: list[str], values: dict[str, float], used: dict[str, int]) -> dict[str, Any]:
    """The changes the researcher's rules allow for what failed, each checked against the parameter's range and its
    largest allowed change. Rejected changes are listed with the reason; nothing is clipped."""
    params = {p.name: p for p in defn.parameters}
    allowed, rejected, stop = [], [], []
    for r in defn.rules:
        if r.when not in failed:
            continue
        if used.get(r.id, 0) >= r.max_uses:
            rejected.append({"rule": r.id, "reason": f"already used {r.max_uses} time(s), the most you allowed"})
            continue
        if r.action == "stop":
            stop.append({"rule": r.id, "reason": r.why or f"you asked to stop when {r.when} fails"})
            continue
        if r.action == "rerun":
            allowed.append({"rule": r.id, "action": "rerun", "why": r.why})
            continue
        prm = params[r.parameter or ""]
        old = values[prm.name]
        new = _apply(r, old)
        if not prm.min <= new <= prm.max:
            rejected.append({"rule": r.id, "reason": f"{prm.label} would become {new:g} {prm.unit}, outside your range "
                                                     f"{prm.min:g}-{prm.max:g} {prm.unit}"})
        elif prm.max_change_factor and old and max(new / old, old / new) > prm.max_change_factor + 1e-9:
            rejected.append({"rule": r.id, "reason": f"a {max(new / old, old / new):.2g}-fold change in {prm.label} is "
                                                     f"more than the {prm.max_change_factor:g}-fold you allowed per run"})
        else:
            allowed.append({"rule": r.id, "action": "change", "parameter": prm.name, "label": prm.label,
                            "unit": prm.unit, "from": old, "to": new, "why": r.why})
    return {"allowed": allowed, "rejected": rejected, "stop": stop}


def choose(cands: dict[str, Any]) -> list[dict[str, Any]]:
    """Rule order decides (the researcher's order): at most one change per parameter in one run."""
    seen, out = set(), []
    for c in cands["allowed"]:
        key = c.get("parameter") or "rerun"
        if key in seen or (key == "rerun" and out):
            continue
        if c["action"] == "rerun" and any(x["action"] == "change" for x in cands["allowed"]):
            continue  # a change already addresses the failure; a plain rerun adds nothing
        seen.add(key)
        out.append(c)
    return out


class AiChoice(BaseModel):
    chosen_rule_ids: list[str]
    reasoning: str


AI_SYSTEM = (
    "You review one run of a laboratory experiment. The researcher defined the criteria and the rules for what may "
    "change after a failure. You get the measured metrics, which criteria failed and the changes the rules allow. "
    "Choose which of the allowed changes to make for the next run (a subset, at most one per parameter), and explain "
    "in plain language why, citing the metric values. You may not propose any change that is not in the allowed "
    "list, change any number, or give clinical advice. If none helps, choose none and say why."
)


def ai_review(client: Any, evaluation: dict[str, Any], cands: dict[str, Any]) -> dict[str, Any]:
    """The AI orders and explains; code keeps only rule ids it was offered (and one change per parameter)."""
    text = json.dumps({"metrics": evaluation["metrics"], "criteria": evaluation["criteria"], "allowed": cands["allowed"]},
                      default=str)
    res = client.parse(AiChoice, system=AI_SYSTEM, input_text=text, prompt_version="loop-review-v1", model_tier="reasoning")
    offered = {c["rule"]: c for c in cands["allowed"]}
    picked, seen = [], set()
    for rid in res.parsed.chosen_rule_ids:
        c = offered.get(rid)
        key = c and (c.get("parameter") or "rerun")
        if c and key not in seen:
            seen.add(key)
            picked.append(c)
    dropped = [r for r in res.parsed.chosen_rule_ids if r not in offered]
    return {"chosen": picked, "reasoning": res.parsed.reasoning.strip(), "model": res.model,
            "dropped_unoffered": dropped, "label": "AI review: chooses only among the changes your rules allow"}


def step(defn: Definition, history: list[dict[str, Any]], readings: dict[str, float] | None, *, label: str,
         client: Any = None) -> dict[str, Any]:
    """One run: plan, (readings), evaluation, then the decision for the next run under the researcher's rules."""
    values = dict(history[-1]["next_values"]) if history else defn.values()
    p = plan(defn, values)
    used: dict[str, int] = {}
    for h in history:
        for c in h["decision"]["changes"]:
            used[c["rule"]] = used.get(c["rule"], 0) + 1
    run: dict[str, Any] = {"run": len(history) + 1, "values": values, "plan": p, "readings_label": label}
    if not p["feasible"]:
        failed = [c["check"] for c in p["checks"] if c["status"] == "fail"]
        run["evaluation"] = {"verdict": "plan_fail", "failed": failed, "criteria": [], "metrics": {}, "fit": None}
    else:
        if readings is None:
            raise ValueError("readings are needed for a run whose plan is feasible")
        ev = evaluate(defn, p, readings)
        failed = [c["id"] for c in ev["criteria"] if not c["pass"]]
        run["evaluation"] = {**ev, "failed": failed}
        run["readings"] = readings
    # independent confirmation: consecutive passing runs with the same settings (a changed setting starts again)
    passes = 0
    for h in [*history, run][::-1]:
        if h["evaluation"]["verdict"] != "pass" or h["values"] != values:
            break
        passes += 1
    cands = candidates(defn, failed, values, used)
    review = None
    if failed and client is not None and cands["allowed"]:
        review = ai_review(client, run["evaluation"], cands)
        changes = review["chosen"]
    else:
        changes = choose(cands) if failed else []
    nxt = dict(values)
    for c in changes:
        if c["action"] == "change":
            nxt[c["parameter"]] = c["to"]
    if passes >= defn.passes_needed:
        status, why = "done", f"{passes} passing runs in a row with the same settings, the number you required"
    elif cands["stop"]:
        status, why = "stopped", cands["stop"][0]["reason"]
    elif len(history) + 1 >= defn.max_runs:
        status, why = "stopped", f"reached the {defn.max_runs}-run limit you set"
    elif failed and not changes:
        status, why = "needs_researcher", "a criterion failed and none of your rules allows a change that fits your ranges"
    else:
        status, why = "continue", "next run queued" + (" with the same settings (a passing run is repeated to confirm it)"
                                                        if not failed else "")
    run["decision"] = {"changes": changes, "rejected": cands["rejected"], "status": status, "why": why,
                       "decided_by": "ai_review" if review else "rules", "ai": review}
    run["next_values"] = nxt
    return run


def overnight(defn: Definition, *, seed: int = 0, client: Any = None, **truth: float) -> dict[str, Any]:
    """The loop with SYNTHETIC readings, run by run until your stop rules end it: what an overnight run would do."""
    history: list[dict[str, Any]] = []
    while True:
        values = history[-1]["next_values"] if history else defn.values()
        p = plan(defn, values, motion=True)
        reads = synthetic_readings(defn, p, seed=seed + len(history), **truth)["readings"] if p["feasible"] else None
        run = step(defn, history, reads, label="SYNTHETIC", client=client)
        history.append(run)
        if run["decision"]["status"] != "continue":
            break
    return {"definition_hash": defn.digest(), "runs": history, "status": history[-1]["decision"]["status"],
            "why": history[-1]["decision"]["why"],
            "label": "SYNTHETIC readings: the loop and the robot plan are real; the plate values are made up by a "
                     "stated model and say nothing about any compound."}


def example_definition() -> Definition:
    """An example dose-response definition (an inhibitor on a luminescence viability readout). Every number is a
    starting point the researcher replaces; defaults follow docs/research/closed_loop_experiments.md."""
    P = Parameter
    return Definition(
        title="Dose-response of a test compound (example)",
        hypothesis="The compound lowers the viability signal in a concentration-dependent way.",
        expected="A full sigmoid curve: a flat top at low concentration, a flat bottom at high concentration, IC50 "
                 "inside the tested range, on plates that pass quality control.",
        parameters=[
            P(name="top_concentration_um", label="Top concentration", unit="uM", value=1.0, min=0.1, max=100,
              max_change_factor=10),
            P(name="dilution_factor", label="Dilution factor", unit="x", value=4.0, min=1.5, max=10, max_change_factor=2),
            P(name="n_concentrations", label="Concentrations", unit="points", role="fixed", value=8, min=4, max=10),
            P(name="replicates", label="Replicates per point", unit="wells", role="fixed", value=3, min=2, max=6),
            P(name="incubation_h", label="Incubation", unit="h", value=1, min=1, max=72, max_change_factor=3),
            P(name="transfer_volume_ul", label="Compound transfer", unit="uL", value=1.0, min=0.5, max=5,
              max_change_factor=2),
            P(name="final_volume_ul", label="Final well volume", unit="uL", role="fixed", value=100, min=20, max=300),
            P(name="stock_concentration_um", label="Stock concentration (in DMSO)", unit="uM", role="fixed",
              value=10000, min=100, max=100000),
            P(name="dmso_max_pct", label="DMSO tolerated by the cells", unit="%", role="fixed", value=1.0, min=0.1,
              max=2),
        ],
        criteria=[
            Criterion(id="plate_quality", metric="z_prime", op=">=", threshold=0.5, severity="technical",
                      why="Z' of 0.5 or more: controls are well separated (Zhang 1999; your choice of threshold)"),
            Criterion(id="vehicle_cv", metric="cv_vehicle_pct", op="<=", threshold=20, severity="technical",
                      why="vehicle controls vary by 20% or less (NIH Assay Guidance Manual)"),
            Criterion(id="curve_fit", metric="fit_r2", op=">=", threshold=0.9, severity="assay",
                      why="the 4-parameter curve describes the points"),
            Criterion(id="top_plateau", metric="points_low_plateau", op=">=", threshold=2, severity="assay",
                      why="2 or more concentrations on the flat top (Sebaugh 2011)"),
            Criterion(id="bottom_plateau", metric="points_high_plateau", op=">=", threshold=2, severity="assay",
                      why="2 or more concentrations on the flat bottom (Sebaugh 2011)"),
        ],
        rules=[
            Rule(id="longer_incubation", when="plate_quality", action="change", parameter="incubation_h",
                 operation="multiply", amount=2, max_uses=2, why="a weak signal window often needs a longer incubation"),
            Rule(id="higher_top", when="bottom_plateau", action="change", parameter="top_concentration_um",
                 operation="multiply", amount=10, max_uses=2, why="no flat bottom: test higher concentrations"),
            Rule(id="wider_steps", when="top_plateau", action="change", parameter="dilution_factor",
                 operation="multiply", amount=1.5, max_uses=2, why="no flat top: spread the series to lower concentrations"),
            Rule(id="less_dmso", when="dmso_limit", action="change", parameter="transfer_volume_ul",
                 operation="multiply", amount=0.5, max_uses=1, why="too much DMSO: transfer less of each dilution"),
            Rule(id="repeat_noisy", when="vehicle_cv", action="rerun", max_uses=1, why="noisy controls: repeat once"),
            Rule(id="repeat_fit", when="curve_fit", action="rerun", max_uses=1, why="a poor fit: repeat once"),
        ],
    )
