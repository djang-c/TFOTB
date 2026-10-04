"""Choose the model provider. OpenAI is the only provider (LLM_PROVIDER may be unset or `openai`).
It needs no vendor package: it is called over plain HTTPS from the standard library.

Recorded responses are cached per provider, so a changed provider never replays another provider's answers.
"""

from __future__ import annotations

import os

from atlas.llm.base import LLMClient, LLMError

PROVIDERS = ("openai",)
KEY_ENV = {"openai": "OPENAI_API_KEY"}


def provider_name() -> str:
    name = (os.environ.get("LLM_PROVIDER") or "openai").strip().lower()
    if name not in PROVIDERS:
        raise LLMError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {name!r}")
    return name


def has_key(provider: str | None = None) -> bool:
    return bool(os.environ.get(KEY_ENV[provider or provider_name()], "").strip())


def make_client(max_tokens: int = 4096) -> LLMClient:
    provider_name()  # refuses an unknown LLM_PROVIDER
    from atlas.llm.openai_client import OpenAIClient

    return OpenAIClient(max_tokens=max_tokens)
