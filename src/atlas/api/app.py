"""FastAPI app factory. Endpoints per docs/implementation/03 §4; P0 stubs return fixtures."""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from atlas import __version__
from atlas.api.experiment_routes import router as experiment_router
from atlas.api.jobs import JobManager
from atlas.api.research_routes import router as research_router
from atlas.api.routes import router
from atlas.api.settings import Settings
from atlas.api.term_routes import LookupLimiter
from atlas.api.term_routes import router as term_router
from atlas.store import PublicStore
from atlas.terms import TermStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Build the real-ontology search index in the background (~5 s) so the first search is fast.
        if settings.real_search:
            from atlas.api.routes import _index_cached
            threading.Thread(target=_index_cached, args=(settings.raw_dir,), daemon=True).start()
        yield

    app = FastAPI(title="The Flight of the Buffalo API", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.jobs = JobManager(max_per_hour=settings.research_max_jobs_per_hour)
    app.state.uploads = PublicStore()  # in memory: a demo session; lost on restart, never merged into the paper store
    app.state.terms = TermStore(settings.store_path.parent)  # verified lookups (atlas.terms); shared, never evidence
    app.state.term_verifier = None  # tests replace this; None means NLM MeSH + Europe PMC
    app.state.lookup_limiter = LookupLimiter()
    app.state.research_runner = None  # tests replace this; None means the real pipeline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(research_router, prefix="/api")
    app.include_router(term_router, prefix="/api")
    app.include_router(experiment_router, prefix="/api")
    if settings.frontend_dist and (settings.frontend_dist / "_shell.html").is_file():
        _serve_frontend(app, settings.frontend_dist)
    return app


def _serve_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built single-page app: real files as they are, every other path as the app shell (client routing)."""
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(status_code=404, detail="Not found")
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            return FileResponse(target)
        return FileResponse(root / "_shell.html")


app = create_app()
