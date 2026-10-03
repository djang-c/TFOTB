"""Record/replay cache so demos and tests run offline and reproducibly.

LLM_MODE: `replay` serves the cache and fails on a miss (never calls the network unless a live
client is supplied and `allow_live_on_miss` is set); `record` always calls live and writes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from atlas.llm.base import LLMClient, LLMError, LLMResult, ModelTier

T = TypeVar("T", bound=BaseModel)


def cache_key(
    provider: str, model_tier: str, prompt_version: str, system: str, input_text: str, schema: str
) -> str:
    blob = json.dumps(
        [provider, model_tier, prompt_version, system, input_text, schema], separators=(",", ":")
    )
    return hashlib.sha256(blob.encode()).hexdigest()


class CachedClient:
    def __init__(
        self,
        inner: LLMClient | None,
        cache_dir: Path,
        mode: Literal["replay", "record"] = "replay",
        allow_live_on_miss: bool = False,
        provider: str | None = None,
    ) -> None:
        self.inner, self.dir, self.mode = inner, Path(cache_dir), mode
        self.allow_live_on_miss = allow_live_on_miss
        # Replay without a live client must name the provider whose recordings it serves.
        self.provider = provider or (inner.provider if inner else "cache-only")

    def parse(
        self,
        schema: type[T],
        *,
        system: str,
        input_text: str,
        prompt_version: str,
        model_tier: ModelTier = "fast",
    ) -> LLMResult:
        key = cache_key(
            self.provider, model_tier, prompt_version, system, input_text, schema.__name__
        )
        path = self.dir / schema.__name__ / f"{key}.json"
        if self.mode == "replay" and path.exists():
            rec = json.loads(path.read_text())
            return LLMResult(
                schema.model_validate(rec["parsed"]),
                rec["provider"],
                rec["model"],
                rec["prompt_version"],
                from_cache=True,
            )
        if self.inner is None or (self.mode == "replay" and not self.allow_live_on_miss):
            raise LLMError(f"replay cache miss ({schema.__name__}/{key[:12]}); no live call made")
        res = self.inner.parse(
            schema,
            system=system,
            input_text=input_text,
            prompt_version=prompt_version,
            model_tier=model_tier,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "parsed": res.parsed.model_dump(mode="json"),
                    "provider": res.provider,
                    "model": res.model,
                    "prompt_version": res.prompt_version,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return res
