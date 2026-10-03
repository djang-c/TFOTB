"""Runtime config from env / .env. Keys documented in env.example (single source)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    fixtures_dir: Path = REPO_ROOT / "data" / "fixtures"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    # Search the pinned ontologies when scripts/fetch_ontologies.py has been run.
    real_search: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
