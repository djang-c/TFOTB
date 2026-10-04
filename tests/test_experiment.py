"""Closed-loop experiment tests. Readings are SYNTHETIC or hand-made (software behaviour only)."""

import math

import pytest
from pydantic import ValidationError

from atlas.experiment import (
    AiChoice,
    Rule,
    candidates,
    evaluate,
    example_definition,
    overnight,
    plan,
    step,
    synthetic_readings,
)


def defn(**changes):
    d = example_definition()
    for p in d.parameters:
        if p.name in changes:
            p.value = changes[p.name]
    return d


def checks(p):
    return {c["check"]: c["status"] for c in p["checks"]}


def test_plan_checks_the_researchers_real_limits():
    ok = plan(defn())
    assert ok["feasible"] and set(checks(ok).values()) == {"pass"}
    assert checks(plan(defn(transfer_volume_ul=2.0), motion=False))["dmso_limit"] == "fail"  # 2 uL in 100 uL = 2% > 1%
    assert checks(plan(defn(transfer_volume_ul=0.5), motion=False))["pipette_range"] == "fail"  # P20 starts at 1 uL
    assert checks(plan(defn(top_concentration_um=100.0, transfer_volume_ul=0.5), motion=False))["stock_limit"] == "fail"
    big = defn()
    next(p for p in big.parameters if p.name == "n_concentrations").value = 9  # 8 columns free on a buffered plate
    assert checks(plan(big, motion=False))["plate_capacity"] == "fail"


def test_the_layout_buffers_the_outer_wells_and_places_controls_and_replicates():
    p = plan(defn(), motion=False)
    roles = [x["role"] for x in p["wells"].values()]
    assert roles.count("buffer") == 36 and roles.count("vehicle") == 6 and roles.count("positive") == 6
    assert roles.count("sample") == 8 * 3 and all(p["wells"][w]["role"] == "buffer" for w in ("A1", "H12", "D1"))


def test_z_prime_and_cv_are_computed_by_the_textbook_formulas():
    d = defn()
    p = plan(d, motion=False)
    reads = {}
    for w, x in p["wells"].items():
        if x["role"] == "vehicle":
            reads[w] = 1000.0 + (10 if w[0] in "BDF" else -10)
        elif x["role"] == "positive":
            reads[w] = 100.0 + (5 if w[0] in "BDF" else -5)
        elif x["role"] == "sample":
            reads[w] = 100 + 900 / (1 + x["conc_um"] / 0.1)
    ev = evaluate(d, p, reads)
    sv, sp = 10 * math.sqrt(6 / 5), 5 * math.sqrt(6 / 5)  # sample SD of +-a alternating over 6 wells
    assert ev["metrics"]["z_prime"] == pytest.approx(1 - 3 * (sv + sp) / 900, rel=1e-9)
    assert ev["metrics"]["cv_vehicle_pct"] == pytest.approx(100 * sv / 1000, rel=1e-9)
    assert ev["fit"]["ic50_um"] == pytest.approx(0.1, rel=0.02) and ev["fit"]["r2"] > 0.999


def test_the_fit_recovers_the_synthetic_ic50():
    d = defn(top_concentration_um=100.0)
    p = plan(d, motion=False)
    ev = evaluate(d, p, synthetic_readings(d, p, seed=3, ic50_um=0.8)["readings"])
    assert ev["fit"]["ic50_um"] == pytest.approx(0.8, rel=0.25) and ev["verdict"] == "pass"


def test_rules_never_go_outside_the_researchers_range_and_nothing_is_clipped():
    d = defn(top_concentration_um=50.0)
    c = candidates(d, ["bottom_plateau"], d.values(), {})
    assert c["allowed"] == [] and "outside your range" in c["rejected"][0]["reason"]  # 500 uM > 100 uM
    d2 = example_definition()
    d2.rules[0] = Rule(id="huge", when="plate_quality", action="change", parameter="incubation_h", operation="multiply",
                       amount=10)
    c2 = candidates(d2, ["plate_quality"], d2.values(), {})
    assert c2["allowed"] == [] and "more than the 3-fold" in c2["rejected"][0]["reason"]
    used = candidates(d, ["top_plateau"], d.values(), {"wider_steps": 2})
    assert "already used 2" in used["rejected"][0]["reason"]


def test_a_rule_may_not_change_a_fixed_parameter():
    d = example_definition().model_dump()
    d["rules"].append({"id": "x", "when": "curve_fit", "action": "change", "parameter": "final_volume_ul",
                       "operation": "add", "amount": 10})
    with pytest.raises(ValidationError, match="fixed by the researcher"):
        type(example_definition()).model_validate(d)


def test_an_infeasible_plan_is_not_run_and_the_dmso_rule_fixes_it():
    d = defn(transfer_volume_ul=2.0)
    run = step(d, [], None, label="SYNTHETIC")
    assert run["evaluation"]["verdict"] == "plan_fail" and "dmso_limit" in run["evaluation"]["failed"]
    assert run["next_values"]["transfer_volume_ul"] == 1.0 and run["decision"]["changes"][0]["rule"] == "less_dmso"


def test_confirmation_needs_consecutive_passes_with_the_same_settings():
    out = overnight(example_definition())
    assert out["status"] == "done" and out["label"].startswith("SYNTHETIC")
    last = out["runs"][-2:]
    assert [r["evaluation"]["verdict"] for r in last] == ["pass", "pass"] and last[0]["values"] == last[1]["values"]
    for r in out["runs"]:  # every run stays inside the researcher's ranges
        for prm in example_definition().parameters:
            assert prm.min <= r["values"][prm.name] <= prm.max


class FakeClient:
    def __init__(self, ids):
        self.ids = ids

    def parse(self, schema, **kw):
        from atlas.llm.base import LLMResult

        return LLMResult(AiChoice(chosen_rule_ids=self.ids, reasoning="Z' is fine; the curve has no bottom."), "fake",
                         "fake-model", kw["prompt_version"])


def test_the_ai_chooses_only_among_the_changes_the_rules_allow():
    d = defn()
    p = plan(d, motion=False)
    reads = synthetic_readings(d, p, seed=1)["readings"]
    run = step(d, [], reads, label="SYNTHETIC", client=FakeClient(["higher_top", "invented_rule", "higher_top"]))
    ai = run["decision"]["ai"]
    assert run["decision"]["decided_by"] == "ai_review" and [c["rule"] for c in ai["chosen"]] == ["higher_top"]
    assert ai["dropped_unoffered"] == ["invented_rule"] and run["next_values"]["top_concentration_um"] == 10.0


def test_api_runs_a_step_with_measured_or_synthetic_readings_and_labels_them(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from atlas.api import create_app
    from atlas.api.settings import Settings

    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    c = TestClient(create_app(Settings(real_search=False, store_path=tmp_path / "atlas.db")))
    d = c.get("/api/experiments/example").json()["definition"]
    assert c.post("/api/experiments/plan", json={"definition": d}).json()["feasible"] is True
    syn = c.post("/api/experiments/step", json={"definition": d, "synthetic_seed": 1, "ai": True}).json()
    assert syn["readings_label"] == "SYNTHETIC" and syn["decided_note"].startswith("rules (no AI key")
    wells = {w: 1000.0 for w, x in syn["plan"]["wells"].items() if x["role"] != "buffer"}
    meas = c.post("/api/experiments/step", json={"definition": d, "readings": wells}).json()
    assert meas["readings_label"] == "MEASURED" and meas["evaluation"]["verdict"] == "technical_fail"  # flat plate
    assert c.post("/api/experiments/step", json={"definition": d}).status_code == 422
    assert c.post("/api/experiments/step", json={"definition": d, "readings": {"Z9": 1.0}}).status_code == 422
    night = c.post("/api/experiments/overnight", json={"definition": d}).json()
    assert night["status"] == "done" and night["label"].startswith("SYNTHETIC")
