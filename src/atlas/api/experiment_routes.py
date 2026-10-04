"""Closed-loop experiment endpoints (atlas.experiment). The researcher's definition travels with every request; the
server keeps no experiment state. Readings are MEASURED (from the researcher's plate reader) or SYNTHETIC (made by a
stated model for showing the loop); the label travels with every run.

AI review (`ai: true`) is used only when a model key is configured and the standing policy allows live calls; the AI
may only choose among the changes the researcher's rules allow. Without a key the rules decide, and the response
says so.
"""

from __future__ import annotations

import math
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas import experiment as ex
from atlas.llm.factory import has_key, make_client
from atlas.policy import IngestPolicy, load_policy

router = APIRouter()
_WELL = re.compile(r"^[A-H](?:[1-9]|1[0-2])$")


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: ex.Definition
    values: dict[str, float] | None = None


class StepBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: ex.Definition
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    readings: dict[str, float] | None = None  # well -> plate-reader value, from the researcher's instrument
    synthetic_seed: int | None = None  # set instead of readings to use SYNTHETIC readings
    ai: bool = False

    @field_validator("readings")
    @classmethod
    def _wells(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return v
        bad = [w for w, x in v.items() if not _WELL.match(w) or not math.isfinite(x)]
        if bad:
            raise ValueError(f"readings need 96-well names (A1-H12) and finite numbers; bad: {bad[:5]}")
        return v


class OvernightBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: ex.Definition
    seed: int = 0
    ai: bool = False


def _policy(request: Request) -> IngestPolicy:
    try:
        return load_policy(request.app.state.settings.policy_path)
    except (OSError, ValueError):
        return IngestPolicy()


def _client(request: Request, wanted: bool) -> tuple[Any, str]:
    if not wanted:
        return None, "rules"
    if not has_key():
        return None, "rules (no AI key is configured, so your rules decided)"
    pol = _policy(request)
    if not pol.live_extraction:
        return None, "rules (live AI calls are off in config/ingest_policy.json)"
    return make_client(max_tokens=pol.max_output_tokens), "ai_review"


@router.get("/experiments/example")
def example() -> dict[str, Any]:
    return {"definition": ex.example_definition().model_dump(mode="json"),
            "note": "An example to start from. Every number is the researcher's to replace.",
            "sources": "docs/research/closed_loop_experiments.md"}


@router.post("/experiments/plan")
def plan(body: PlanBody) -> dict[str, Any]:
    return ex.plan(body.definition, body.values)


@router.post("/experiments/step")
def step(request: Request, body: StepBody) -> dict[str, Any]:
    if len(body.history) >= body.definition.max_runs:
        raise HTTPException(status_code=409, detail=f"the {body.definition.max_runs}-run limit is reached")
    values = body.history[-1]["next_values"] if body.history else body.definition.values()
    p = ex.plan(body.definition, values, motion=False)
    readings, label = body.readings, "MEASURED"
    if readings is None and p["feasible"]:
        if body.synthetic_seed is None:
            raise HTTPException(status_code=422, detail="send the plate-reader readings, or ask for synthetic ones")
        readings, label = ex.synthetic_readings(body.definition, p, seed=body.synthetic_seed)["readings"], "SYNTHETIC"
    client, mode = _client(request, body.ai)
    run = ex.step(body.definition, body.history, readings, label=label, client=client)
    run["decided_note"] = mode
    return run


@router.post("/experiments/overnight")
def overnight(request: Request, body: OvernightBody) -> dict[str, Any]:
    client, mode = _client(request, body.ai)
    out = ex.overnight(body.definition, seed=body.seed, client=client)
    out["decided_note"] = mode
    return out

