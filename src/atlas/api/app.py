"""FastAPI app factory. Endpoints per docs/implementation/03 §4; P0 stubs return fixtures."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.jobs import JobManager
from atlas.api.research_routes import router as research_router
from atlas.api.routes import router
from atlas.api.settings import Settings


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
    app.state.research_runner = None  # tests replace this; None means the real pipeline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(research_router, prefix="/api")
    return app


app = create_app()
