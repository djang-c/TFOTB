"""Choose the model provider from the environment (LLM_PROVIDER = anthropic | openai; default anthropic).

Recorded responses are cached per provider, so switching provider never replays another provider's answers.
"""

from __future__ import annotations

import os

from atlas.llm.base import LLMClient, LLMError

PROVIDERS = ("anthropic", "openai")
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def provider_name() -> str:
    name = (os.environ.get("LLM_PROVIDER") or "anthropic").strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {name!r}")
    return name


def has_key(provider: str | None = None) -> bool:
    return bool(os.environ.get(KEY_ENV[provider or provider_name()], "").strip())


def make_client(max_tokens: int = 4096) -> LLMClient:
    if provider_name() == "openai":
        from atlas.llm.openai_client import OpenAIClient

        return OpenAIClient(max_tokens=max_tokens)
    from atlas.llm.anthropic_client import AnthropicClient

    return AnthropicClient(max_tokens=max_tokens)
