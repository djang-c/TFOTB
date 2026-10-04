"""Standing ingest policy (config/ingest_policy.json): the one place that says what may run unattended.

The owner sets this once. A scheduled run reads it and needs no per-run approval. The caps are the
spending control; live model calls happen only when the policy allows them AND a key is in the
environment (no key means replay-only, never an error and never a silent skip).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class IngestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    readme: str = Field(default="", alias="_readme")
    live_extraction: bool = False
    max_papers_per_run: int = Field(default=5, ge=1, le=200)
    max_chars_per_paper: int = Field(default=70_000, ge=1_000)
    max_output_tokens: int = Field(default=4096, ge=256)
    seed_entities: tuple[str, ...] = ()
    extra_queries: tuple[str, ...] = ()
    max_hypotheses_per_run: int = Field(default=10, ge=1, le=100)
    discovery_per_query: int = Field(default=10, ge=1, le=100)
    only_licences: tuple[str, ...] | None = None


def load_policy(path: Path) -> IngestPolicy:
    """The policy file, or the safe default (replay-only) when it does not exist."""
    if not path.exists():
        return IngestPolicy()
    return IngestPolicy.model_validate(json.loads(path.read_text()))
