"""Provider-agnostic LLM layer (docs/implementation/06-ai-layer.md).

The model proposes, code disposes: services depend on `LLMClient`, never on a vendor SDK.
Anthropic is the provider for now; an OpenAI adapter is added at deployment (see DECISIONS.md).
"""

from atlas.llm.base import LLMClient, LLMError, LLMRefusal, LLMResult
from atlas.llm.cache import CachedClient, cache_key

__all__ = ["CachedClient", "LLMClient", "LLMError", "LLMRefusal", "LLMResult", "cache_key"]
