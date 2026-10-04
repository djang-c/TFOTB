"""Anthropic adapter tests with fake HTTP (no network, no key). Live behaviour is UNVERIFIED."""

import json

import pytest

from atlas.extraction import ExtractionOutput
from atlas.hypotheses import HypothesisOutput
from atlas.llm.anthropic_client import AnthropicClient, anthropic_schema
from atlas.llm.base import LLMError, LLMRefusal


class Spy:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, url, body, headers):
        self.calls.append((url, body, headers))
        return self.reply


def reply(text=None, stop="end_turn"):
    content = [{"type": "thinking", "thinking": "..."}] + ([{"type": "text", "text": text}] if text is not None else [])
    return {"stop_reason": stop, "content": content}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    for k in ("ANTHROPIC_MODEL_FAST", "ANTHROPIC_MODEL_REASONING"):
        monkeypatch.delenv(k, raising=False)


def test_request_uses_structured_output_the_key_header_and_marks_the_text_as_data():
    spy = Spy(reply(json.dumps({"statements": []})))
    res = AnthropicClient(post=spy).parse(ExtractionOutput, system="SYS", input_text="PAPER", prompt_version="v")
    url, body, headers = spy.calls[0]
    assert url.endswith("/v1/messages") and headers["x-api-key"] == "sk-ant-test-not-real"
    assert headers["anthropic-version"] == "2023-06-01"
    assert body["model"] == "claude-sonnet-5-5" and body["system"] == "SYS"
    assert body["output_config"]["format"]["type"] == "json_schema" and "<untrusted_data>" in body["messages"][0]["content"]
    assert res.provider == "anthropic" and res.model == "claude-sonnet-5-5" and res.parsed.statements == []


def test_reasoning_tier_uses_opus_and_env_overrides_the_model(monkeypatch):
    spy = Spy(reply(json.dumps({"hypotheses": []})))
    AnthropicClient(post=spy).parse(HypothesisOutput, system="S", input_text="x", prompt_version="v", model_tier="reasoning")
    assert spy.calls[0][1]["model"] == "claude-opus-5-5"
    monkeypatch.setenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")
    assert AnthropicClient().model_for("fast") == "claude-haiku-4-5-20251001"


@pytest.mark.parametrize("model", [ExtractionOutput, HypothesisOutput])
def test_schema_has_no_unsupported_keywords_and_forbids_extra_keys(model):
    text = json.dumps(anthropic_schema(model))
    for bad in ('"minLength"', '"maxLength"', '"minItems"', '"maxItems"', '"minimum"', '"maximum"', '"default"'):
        assert bad not in text
    assert '"additionalProperties": true' not in text


def test_refusal_cut_off_empty_and_malformed_answers_are_errors():
    with pytest.raises(LLMRefusal):
        AnthropicClient(post=Spy(reply("{}", stop="refusal"))).parse(ExtractionOutput, system="", input_text="", prompt_version="v")
    with pytest.raises(LLMError, match="cut off"):
        AnthropicClient(post=Spy(reply("{", stop="max_tokens"))).parse(ExtractionOutput, system="", input_text="", prompt_version="v")
    with pytest.raises(LLMError, match="no output"):
        AnthropicClient(post=Spy(reply(None))).parse(ExtractionOutput, system="", input_text="", prompt_version="v")
    with pytest.raises(LLMError, match="does not match"):
        AnthropicClient(post=Spy(reply("not json"))).parse(ExtractionOutput, system="", input_text="", prompt_version="v")


def test_a_missing_key_is_an_error_and_the_key_never_appears_in_errors(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY is not set"):
        AnthropicClient(post=Spy(reply("{}"))).parse(ExtractionOutput, system="", input_text="", prompt_version="v")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")

    def boom(url, body, headers):
        raise LLMError("Anthropic API returned HTTP 401")

    with pytest.raises(LLMError) as e:
        AnthropicClient(post=boom).parse(ExtractionOutput, system="", input_text="", prompt_version="v")
    assert "sk-ant-secret" not in str(e.value)
