"""T23: a recorded simulation run as a graph-linked engineering artifact.

A `SimulationRun` restates what `robotics/simulate.py` wrote (spec hash, scene hash, simulator version,
review state, checks, failures) and records which stored claims the specification traces to. It is
linked into the graph by one `SIMULATES_WORKFLOW_FOR` claim. That claim is labelled
`computational_prediction`, is never reviewed by this code, and never counts as biological support
(`ranking.categorize` ignores the predicate). A passing run therefore cannot move any ranking.

The run refuses to exist unless biology and physical execution are marked `not_modeled`.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas.schemas import Claim, ClaimStatus, CurieStr, ReviewState, SourceType

NOT_MODELED = ("biology", "physical_execution")
_SLUG = re.compile(r"[A-Za-z0-9_.-]+")


class SimulationError(ValueError):
    pass


class SimulationRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: CurieStr  # SIM:<slug>
    experiment_spec_hash: str = Field(min_length=8)
    scene_hash: str = Field(min_length=8)
    simulator_name: str
    simulator_version: str
    adapter_version: str
    random_seed: int
    spec_review_state: str  # verbatim from the spec, e.g. "generic_fixture_unreviewed"
    source_claim_ids: tuple[CurieStr, ...] = ()
    overall: str
    checks: tuple[dict[str, Any], ...]
    failures: tuple[dict[str, Any], ...] = ()
    simulation_steps: int | None = None
    path_length_mm: float | None = None
    simulation_time_note: str = "kinematic samples; not physical time"
    scope_label: str
    biology: str = "not_modeled"
    physical_validation: str = "absent"

    @field_validator("run_id")
    @classmethod
    def _sim(cls, v: str) -> str:
        if not v.startswith("SIM:"):
            raise ValueError("run_id must be a SIM: id")
        return v

    @field_validator("overall")
    @classmethod
    def _overall(cls, v: str) -> str:
        if v not in {"pass", "fail"}:
            raise ValueError("overall must be 'pass' or 'fail'")
        return v

    @model_validator(mode="after")
    def _honest(self) -> SimulationRun:
        status = {c.get("check_name"): c.get("status") for c in self.checks}
        wrong = [n for n in NOT_MODELED if status.get(n) != "not_modeled"]
        if wrong:
            raise ValueError(f"checks must mark {wrong} as not_modeled")
        if "not wet-lab validated" not in self.scope_label:
            raise ValueError("scope_label must say the run is not wet-lab validated")
        if self.overall == "pass" and self.failures:
            raise ValueError("a run with recorded failures cannot be 'pass'")
        if self.biology != "not_modeled" or self.physical_validation != "absent":
            raise ValueError("biology must be not_modeled and physical validation absent")
        return self


_REQUIRED = ("run_id", "experiment_spec_hash", "scene_hash", "simulator_name", "simulator_version",
             "adapter_version", "random_seed", "review_state", "overall", "checks", "scope_label")


def run_from_report(report: dict[str, Any], source_claim_ids: tuple[str, ...] = ()) -> SimulationRun:
    missing = [k for k in _REQUIRED if k not in report]
    if missing:
        raise SimulationError(f"simulation report is missing {missing}")
    slug = str(report["run_id"])
    if not _SLUG.fullmatch(slug):
        raise SimulationError(f"unusable run id {slug!r}")
    return SimulationRun(
        run_id=f"SIM:{slug}", experiment_spec_hash=report["experiment_spec_hash"], scene_hash=report["scene_hash"],
        simulator_name=report["simulator_name"], simulator_version=report["simulator_version"],
        adapter_version=report["adapter_version"], random_seed=report["random_seed"],
        spec_review_state=report["review_state"], source_claim_ids=tuple(source_claim_ids),
        overall=report["overall"], checks=tuple(report["checks"]), failures=tuple(report.get("failures", [])),
        simulation_steps=report.get("simulation_steps"), path_length_mm=report.get("path_length_mm"),
        simulation_time_note=report.get("simulation_time_note", "kinematic samples; not physical time"),
        scope_label=report["scope_label"],
    )


def link_claim(run: SimulationRun, entity_id: str, claims: dict[str, Claim] | None = None) -> Claim:
    """The one graph edge for a run: SIM -> entity, predicate SIMULATES_WORKFLOW_FOR.

    If `claims` is given, every source claim of the run must be in it (nothing untraceable is linked).
    """
    if claims is not None:
        absent = [i for i in run.source_claim_ids if i not in claims]
        if absent:
            raise SimulationError(f"source claims not in the store: {absent}")
    slug = run.run_id.removeprefix("SIM:")
    return Claim(
        claim_id=f"CLAIM:sim-{slug}-{entity_id.replace(':', '-')}",
        subject_id=run.run_id,
        predicate="SIMULATES_WORKFLOW_FOR",
        object_id=entity_id,
        source_url=f"local:robotics/simulate.py#{slug}",
        source_span=f"{run.scope_label}; spec {run.experiment_spec_hash}; {run.simulator_name} {run.simulator_version}",
        source_type=SourceType.synthetic_fixture,  # generic illustrative specs; no engineering source type yet
        status=ClaimStatus.computational_prediction,
        review_state=ReviewState.unreviewed,
        lineage_id=f"STUDY:sim-{slug}",
        context={"overall": run.overall, "spec_review_state": run.spec_review_state, "scene_hash": run.scene_hash},
        derived_from=run.source_claim_ids,
        extraction_method=f"simulation:{run.simulator_name}@{run.simulator_version}",
    )
