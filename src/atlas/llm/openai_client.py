"""OpenAI adapter (Chat Completions with strict JSON-schema output), using only the standard library.

STATUS: written to OpenAI's published structured-outputs request shape and tested offline against fake
responses. It has NOT been run against the live API from this repository (no key was used), so treat live
behaviour as UNVERIFIED until one approved call has been made and the result checked.

No model name is hard-coded. Set OPENAI_MODEL_FAST and OPENAI_MODEL_REASONING (a model that supports
structured outputs) and OPENAI_API_KEY. A missing model name is an error, never a guess. The key is read from
the environment, sent only in the Authorization header, and never logged or echoed in errors.
The text to analyse is delimited and declared to be data, exactly as in the Anthropic adapter.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from atlas.llm.base import LLMError, LLMRefusal, LLMResult, ModelTier

T = TypeVar("T", bound=BaseModel)
API_BASE = "https://api.openai.com/v1"
ENV_MODELS = {"reasoning": "OPENAI_MODEL_REASONING", "fast": "OPENAI_MODEL_FAST"}
Post = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


def strict_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """A pydantic model's JSON schema made acceptable to strict structured outputs: every object forbids extra
    keys and lists all its properties as required; unsupported keywords (default, title) are dropped."""

    def fix(node: Any) -> Any:
        if isinstance(node, list):
            return [fix(x) for x in node]
        if not isinstance(node, dict):
            return node
        out = {k: fix(v) for k, v in node.items() if k not in {"default", "title"}}
        if out.get("type") == "object" or "properties" in out:
            props = out.get("properties", {})
            out["additionalProperties"] = False
            out["required"] = list(props)
        return out

    return fix(schema.model_json_schema())


def _http_post(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise LLMError(f"OpenAI API returned HTTP {exc.code}") from exc  # the body is not echoed
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise LLMError(f"OpenAI API call failed: {type(exc).__name__}") from exc


class OpenAIClient:
    provider = "openai"

    def __init__(self, max_tokens: int = 4096, *, post: Post | None = None, api_base: str = API_BASE) -> None:
        self.max_tokens, self._post, self._base = max_tokens, post or _http_post, api_base

    def model_for(self, tier: ModelTier) -> str:
        name = os.environ.get(ENV_MODELS[tier], "").strip()
        if not name:
            raise LLMError(f"{ENV_MODELS[tier]} is not set; no OpenAI model is assumed")
        return name

    def parse(
        self, schema: type[T], *, system: str, input_text: str, prompt_version: str, model_tier: ModelTier = "fast"
    ) -> LLMResult:
        model = self.model_for(model_tier)
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise LLMError("OPENAI_API_KEY is not set")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"<untrusted_data>\n{input_text}\n</untrusted_data>"},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": strict_schema(schema)},
            },
            "max_completion_tokens": self.max_tokens,
        }
        data = self._post(
            f"{self._base}/chat/completions", body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        )
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected response shape from {model}") from exc
        if message.get("refusal"):
            raise LLMRefusal(f"{model} refused ({schema.__name__})")
        if choice.get("finish_reason") == "length":
            raise LLMError(f"{model} output was cut off at {self.max_tokens} tokens ({schema.__name__})")
        content = message.get("content")
        if not content:
            raise LLMError(f"no output from {model} ({schema.__name__})")
        try:
            parsed = schema.model_validate_json(content)
        except ValueError as exc:
            raise LLMError(f"{model} returned output that does not match {schema.__name__}") from exc
        return LLMResult(parsed, self.provider, model, prompt_version)
