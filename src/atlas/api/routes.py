"""P0 stub routes: every endpoint in docs/implementation/03 §4, serving SYNTHETIC fixtures.

Path parameters are accepted but ignored until the real services land (T02-T12).
"""

from typing import Any

from fastapi import APIRouter, Request

from atlas.api.fixtures import load_fixture

router = APIRouter()


def _fx(request: Request, name: str) -> Any:
    return load_fixture(request.app.state.settings.fixtures_dir, name)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta")
def meta(request: Request) -> Any:
    return _fx(request, "meta")


@router.get("/search")
def search(request: Request, q: str) -> Any:
    return _fx(request, "search")


@router.get("/entities/{entity_id}")
def entity(request: Request, entity_id: str) -> Any:
    return _fx(request, "entity")


@router.get("/entities/{entity_id}/connections")
def connections(request: Request, entity_id: str) -> Any:
    return _fx(request, "connections")


@router.get("/entities/{entity_id}/assets")
def assets(request: Request, entity_id: str) -> Any:
    return _fx(request, "assets")


@router.get("/entities/{entity_id}/collaborators")
def collaborators(request: Request, entity_id: str) -> Any:
    return _fx(request, "collaborators")


@router.get("/entities/{entity_id}/graph")
def graph(request: Request, entity_id: str, max_nodes: int = 40) -> Any:
    return _fx(request, "graph")


@router.get("/entities/{entity_id}/gap")
def gap(request: Request, entity_id: str) -> Any:
    return _fx(request, "gap")


@router.get("/claims/{claim_id}")
def claim(request: Request, claim_id: str) -> Any:
    return _fx(request, "claim")


@router.post("/explain")
def explain(request: Request) -> Any:
    return _fx(request, "explain")


@router.post("/actions")
def actions(request: Request) -> Any:
    return _fx(request, "action")


@router.post("/uploads")
def uploads(request: Request) -> Any:
    return _fx(request, "upload")


@router.get("/simulations/{run_id}")
def simulation(request: Request, run_id: str) -> Any:
    return _fx(request, "simulation")
