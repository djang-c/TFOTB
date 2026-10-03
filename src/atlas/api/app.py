"""FastAPI app factory. Endpoints per docs/implementation/03 §4; P0 stubs return fixtures."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
