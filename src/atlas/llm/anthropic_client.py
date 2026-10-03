"""Anthropic adapter (provider for now; OpenAI adapter at deployment).

UNVERIFIED: written to docs/implementation/06-ai-layer.md section 0 (`messages.parse(...,
output_format=Schema)` -> `parsed_output`). The `anthropic` SDK is not installed in this
environment, so this adapter has NOT been executed and its SDK calls are unchecked against the
installed SDK version. Install and review the package (needs human approval), run one approved
live call, and pin model + prompt + schema in DECISIONS.md before relying on it.
Model IDs come from env (LLM_MODEL_REASONING / LLM_MODEL_FAST), never hard-coded into services.
"""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from atlas.llm.base import LLMError, LLMRefusal, LLMResult, ModelTier

T = TypeVar("T", bound=BaseModel)
DEFAULT_MODELS = {"reasoning": "claude-opus-5-5", "fast": "claude-sonnet-5-5"}
ENV_MODELS = {"reasoning": "LLM_MODEL_REASONING", "fast": "LLM_MODEL_FAST"}


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, max_tokens: int = 4096) -> None:
        try:
            import anthropic  # lazy: keeps the package optional
        except ImportError as exc:
            raise LLMError(
                "`anthropic` is not installed (optional dependency: pip install .[llm])"
            ) from exc
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        self.max_tokens = max_tokens

    def model_for(self, tier: ModelTier) -> str:
        return os.environ.get(ENV_MODELS[tier], DEFAULT_MODELS[tier])

    def parse(
        self,
        schema: type[T],
        *,
        system: str,
        input_text: str,
        prompt_version: str,
        model_tier: ModelTier = "fast",
    ) -> LLMResult:
        model = self.model_for(model_tier)
        # Untrusted text is delimited and declared to be data, not instructions.
        user = f"<untrusted_data>\n{input_text}\n</untrusted_data>"
        resp = self._client.messages.parse(
            model=model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise LLMRefusal(f"{model} refused ({schema.__name__})")
        parsed = resp.parsed_output
        if parsed is None:
            raise LLMError(f"no parsed output from {model} ({schema.__name__})")
        return LLMResult(schema.model_validate(parsed), self.provider, model, prompt_version)
