"""Anthropic adapter (Messages API with JSON-schema structured output), using only the standard library.

Owner decision 2026-10-04: run paper research with the Anthropic key. No Anthropic package is installed: the call
is plain HTTPS, as for OpenAI. Request shape: POST /v1/messages with `output_config.format` =
{"type": "json_schema", "schema": ...} (Anthropic's documented structured-output parameter). Tested offline against
fake responses; live behaviour is UNVERIFIED until the first real run is checked.

Models: ANTHROPIC_MODEL_FAST (default claude-sonnet-5-5) and ANTHROPIC_MODEL_REASONING (default claude-opus-5-5).
The key is read from ANTHROPIC_API_KEY, sent only in the x-api-key header, and never logged or echoed in errors.
The text to analyse is delimited and declared to be data (see wrap_untrusted).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from atlas.llm.base import LLMError, LLMRefusal, LLMResult, ModelTier, wrap_untrusted
from atlas.llm.openai_client import strict_schema

T = TypeVar("T", bound=BaseModel)
API_BASE = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"
DEFAULT_MODELS = {"reasoning": "claude-opus-5-5", "fast": "claude-sonnet-5-5"}
ENV_MODELS = {"reasoning": "ANTHROPIC_MODEL_REASONING", "fast": "ANTHROPIC_MODEL_FAST"}
EFFORT = {"reasoning": "medium", "fast": "low"}  # thinking depth; keeps extraction cheap
# Structured outputs do not accept these keywords; pydantic still checks them on the parsed result.
_UNSUPPORTED = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems"}
Post = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


def anthropic_schema(schema: type[BaseModel]) -> dict[str, Any]:
    def strip(node: Any) -> Any:
        if isinstance(node, list):
            return [strip(x) for x in node]
        if not isinstance(node, dict):
            return node
        return {k: strip(v) for k, v in node.items() if k not in _UNSUPPORTED}

    return strip(strict_schema(schema))


def _http_post(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise LLMError(f"Anthropic API returned HTTP {exc.code}") from exc  # the body is not echoed
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise LLMError(f"Anthropic API call failed: {type(exc).__name__}") from exc


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, max_tokens: int = 4096, *, post: Post | None = None, api_base: str = API_BASE) -> None:
        self.max_tokens, self._post, self._base = max_tokens, post or _http_post, api_base

    def model_for(self, tier: ModelTier) -> str:
        return os.environ.get(ENV_MODELS[tier], "").strip() or DEFAULT_MODELS[tier]

    def parse(
        self, schema: type[T], *, system: str, input_text: str, prompt_version: str, model_tier: ModelTier = "fast"
    ) -> LLMResult:
        model = self.model_for(model_tier)
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        body = {
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": wrap_untrusted(input_text)}],
            "output_config": {"effort": EFFORT[model_tier],
                              "format": {"type": "json_schema", "schema": anthropic_schema(schema)}},
        }
        data = self._post(f"{self._base}/messages", body,
                          {"x-api-key": key, "anthropic-version": API_VERSION, "content-type": "application/json"})
        stop = data.get("stop_reason") if isinstance(data, dict) else None
        if stop == "refusal":
            raise LLMRefusal(f"{model} refused ({schema.__name__})")
        if stop == "max_tokens":
            raise LLMError(f"{model} output was cut off at {self.max_tokens} tokens ({schema.__name__}); "
                           "raise max_output_tokens in config/ingest_policy.json")
        try:
            text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise LLMError(f"unexpected response shape from {model}") from exc
        if not text.strip():
            raise LLMError(f"no output from {model} ({schema.__name__})")
        try:
            parsed = schema.model_validate_json(text)
        except ValueError as exc:
            raise LLMError(f"{model} returned output that does not match {schema.__name__}") from exc
        return LLMResult(parsed, self.provider, model, prompt_version)
