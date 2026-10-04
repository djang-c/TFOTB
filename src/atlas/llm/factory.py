"""Choose the model provider: LLM_PROVIDER = anthropic | openai. Without it, Anthropic is used when
ANTHROPIC_API_KEY is set, else OpenAI (owner decision 2026-10-04: research runs with the Anthropic key).
Neither provider needs a vendor package: both are called over plain HTTPS from the standard library.

Recorded responses are cached per provider, so a changed provider never replays another provider's answers.
"""

from __future__ import annotations

import os

from atlas.llm.base import LLMClient, LLMError

PROVIDERS = ("anthropic", "openai")
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def provider_name() -> str:
    name = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if not name:
        return "anthropic" if os.environ.get("ANTHROPIC_API_KEY", "").strip() else "openai"
    if name not in PROVIDERS:
        raise LLMError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {name!r}")
    return name


def has_key(provider: str | None = None) -> bool:
    return bool(os.environ.get(KEY_ENV[provider or provider_name()], "").strip())


def make_client(max_tokens: int = 4096) -> LLMClient:
    if provider_name() == "anthropic":
        from atlas.llm.anthropic_client import AnthropicClient

        return AnthropicClient(max_tokens=max_tokens)
    from atlas.llm.openai_client import OpenAIClient

    return OpenAIClient(max_tokens=max_tokens)
