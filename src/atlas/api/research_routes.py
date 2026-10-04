"""On-demand research: a user asks about a disease or a topic and the system goes and reads the literature.

POST /api/research starts a background job (find credible open-access papers, extract claims, store
them) and returns a job ID at once; GET /api/research/{job_id} reports progress and, when done, what
was stored. The caps and the live/replay decision come from the standing policy file, never from the
request. The endpoint is OFF unless the server sets `research_enabled`, because a live run can spend
money; an optional token (`research_token`) must then be sent as `X-Research-Token`.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from atlas.api.jobs import RateLimited
from atlas.api.routes import _entity
from atlas.llm.cache import CachedClient
from atlas.llm.factory import make_client, provider_name
from atlas.policy import load_policy
from atlas.research import ResearchUnavailable, live_allowed, load_extraction_resolver, run_research

router = APIRouter()
MAX_TERMS = 3


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=200)
    entity_id: str | None = Field(default=None, max_length=60)


def _token_ok(request: Request, token: str | None) -> bool:
    expected = request.app.state.settings.research_token
    # compare as bytes: a non-ASCII header must be a 401, not a crash (hmac.compare_digest needs ASCII str)
    return bool(expected) and hmac.compare_digest((token or "").encode("utf-8"), expected.encode("utf-8"))


def _guard(request: Request, token: str | None) -> None:
    s = request.app.state.settings
    if not s.research_enabled:
        raise HTTPException(status_code=403, detail="On-demand research is turned off on this server.")
    if not s.research_token:  # fail closed: this endpoint can spend money, so it never runs unauthenticated
        raise HTTPException(status_code=503, detail="Research is enabled but not configured on this server, so it will not run.")
    if not _token_ok(request, token):
        raise HTTPException(status_code=401, detail="Missing or wrong research token.")


def _default_work(request: Request, terms: list[str]) -> Any:
    s = request.app.state.settings
    policy = load_policy(s.policy_path)

    def work() -> dict[str, Any]:
        resolver = load_extraction_resolver(s.raw_dir)  # raises ResearchUnavailable with a plain message
        live = live_allowed(policy)
        inner = make_client(max_tokens=policy.max_output_tokens) if live else None
        cache = s.store_path.parent.parent / "cache" / "llm"
        client = CachedClient(inner, cache, mode="replay", allow_live_on_miss=live, provider=provider_name())
        return run_research(
            terms=terms, pmids=None, policy=policy, store_dir=s.store_path.parent, client=client,
            resolver=resolver, live=live,
        )

    return work


@router.get("/research")
def research_status(request: Request, x_research_token: str | None = Header(default=None)) -> dict[str, Any]:
    s = request.app.state.settings
    policy = load_policy(s.policy_path)
    return {
        "enabled": s.research_enabled,
        "needs_token": bool(s.research_token),
        "live_model_calls": policy.live_extraction and s.research_enabled,
        "max_papers_per_job": policy.max_papers_per_run,
        "max_jobs_per_hour": s.research_max_jobs_per_hour,
        "sources": "PubMed-indexed journal articles with open-access full text; preprints, retractions and editorials are excluded",
        # job terms and results are only shown to a caller who holds the token
        "recent_jobs": [j.public() for j in request.app.state.jobs.recent()] if s.research_enabled and _token_ok(request, x_research_token) else [],
    }


@router.post("/research", status_code=202)
def start_research(
    request: Request, body: ResearchRequest, x_research_token: str | None = Header(default=None)
) -> dict[str, Any]:
    _guard(request, x_research_token)
    terms: list[str] = []
    if body.entity_id:
        label = _entity(request, body.entity_id).get("label", "")  # 404 if the entity is not indexed
        if label:
            terms.append(label)
    if body.query and body.query.strip():
        terms.append(" ".join(body.query.split()))
    if not terms:
        raise HTTPException(status_code=422, detail="Give a query, or an entity_id that has a name.")
    terms = terms[:MAX_TERMS]
    runner = request.app.state.research_runner or _default_work
    try:
        job = request.app.state.jobs.submit(terms, runner(request, terms))
    except RateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return job.public()


@router.get("/research/{job_id}")
def research_job(request: Request, job_id: str, x_research_token: str | None = Header(default=None)) -> dict[str, Any]:
    _guard(request, x_research_token)
    job = request.app.state.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"no research job {job_id}")
    return job.public()


__all__ = ["ResearchUnavailable", "router"]
