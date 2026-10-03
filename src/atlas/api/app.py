"""FastAPI app factory. Endpoints per docs/implementation/03 §4; P0 stubs return fixtures."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.routes import router
from atlas.api.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="TFOTB API", version=__version__)
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
