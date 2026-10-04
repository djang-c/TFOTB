"""LLM client interface. No vendor SDK is imported here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
ModelTier = Literal["fast", "reasoning"]


def wrap_untrusted(text: str) -> str:
    """Delimit text that is DATA. A literal closing tag inside it is defused so the text cannot end its own wrapper."""
    safe = text.replace("</untrusted_data>", "<\\/untrusted_data>").replace("<untrusted_data>", "<\\untrusted_data>")
    return f"<untrusted_data>\n{safe}\n</untrusted_data>"


class LLMError(RuntimeError):
    """Provider failure, or a replay-mode cache miss with no live fallback."""


class LLMRefusal(LLMError):
    """The model refused (e.g. a safety classifier on biomedical text). Callers mark the item
    'not extracted' and continue; they must never fabricate output."""


@dataclass(frozen=True)
class LLMResult:
    parsed: BaseModel
    provider: str
    model: str
    prompt_version: str
    from_cache: bool = False  # replayed responses must be labelled `cached` in the UI


class LLMClient(Protocol):
    provider: str

    def parse(
        self,
        schema: type[T],
        *,
        system: str,
        input_text: str,
        prompt_version: str,
        model_tier: ModelTier = "fast",
    ) -> LLMResult:
        """Return `schema`-validated output. `input_text` is untrusted DATA, never instructions."""
        ...
