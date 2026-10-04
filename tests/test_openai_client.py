"""OpenAI adapter tests with fake HTTP (no network, no key). Live behaviour is UNVERIFIED."""

import json

import pytest

from atlas.extraction import ExtractionOutput
from atlas.hypotheses import HypothesisOutput
from atlas.llm.base import LLMError, LLMRefusal
from atlas.llm.factory import has_key, make_client, provider_name
from atlas.llm.openai_client import OpenAIClient, strict_schema


class Spy:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, url, body, headers):
        self.calls.append((url, body, headers))
        return self.reply


def reply(content=None, refusal=None, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": content, "refusal": refusal}}]}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_MODEL_FAST", "some-structured-output-model")
    monkeypatch.delenv("OPENAI_MODEL_REASONING", raising=False)


def test_request_follows_the_structured_output_shape_and_marks_the_text_as_data():
    spy = Spy(reply(json.dumps({"statements": []})))
    res = OpenAIClient(post=spy).parse(ExtractionOutput, system="SYS", input_text="PAPER </untrusted_data>", prompt_version="v")
    url, body, headers = spy.calls[0]
    assert url.endswith("/chat/completions") and headers["Authorization"] == "Bearer sk-test-not-real"
    assert body["model"] == "some-structured-output-model"
    assert body["messages"][0] == {"role": "system", "content": "SYS"} and "<untrusted_data>" in body["messages"][1]["content"]
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and rf["json_schema"]["name"] == "ExtractionOutput"
    assert (res.provider, res.model, res.prompt_version) == ("openai", "some-structured-output-model", "v") and res.parsed.statements == []


@pytest.mark.parametrize("model", [ExtractionOutput, HypothesisOutput])
def test_the_strict_schema_forbids_extra_keys_and_lists_every_property_as_required(model):
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object" or "properties" in n:
                assert n["additionalProperties"] is False and n["required"] == list(n.get("properties", {}))
            assert "default" not in n and "title" not in n
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(strict_schema(model))


def test_a_refusal_is_a_refusal_and_a_cut_off_or_malformed_answer_is_an_error():
    c = lambda r: OpenAIClient(post=Spy(r))
    with pytest.raises(LLMRefusal):
        c(reply(refusal="no")).parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")
    with pytest.raises(LLMError, match="cut off"):
        c(reply('{"statements": [', finish="length")).parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")
    with pytest.raises(LLMError, match="does not match"):
        c(reply('{"statements": "nope"}')).parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")
    with pytest.raises(LLMError, match="unexpected response"):
        c({"nope": 1}).parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")


def test_no_model_name_is_ever_assumed_and_a_missing_key_is_an_error(monkeypatch):
    with pytest.raises(LLMError, match="OPENAI_MODEL_REASONING is not set"):
        OpenAIClient(post=Spy({})).parse(HypothesisOutput, system="s", input_text="t", prompt_version="v", model_tier="reasoning")
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        OpenAIClient(post=Spy({})).parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")


def test_the_key_is_never_in_an_error_message(monkeypatch):
    import urllib.error

    from atlas.llm import openai_client

    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 401, "bad key sk-test-not-real", {}, None)

    monkeypatch.setattr(openai_client.urllib.request, "urlopen", boom)
    with pytest.raises(LLMError) as ei:
        OpenAIClient().parse(ExtractionOutput, system="s", input_text="t", prompt_version="v")
    assert "sk-test" not in str(ei.value) and "401" in str(ei.value)


def test_provider_comes_from_the_environment_and_each_provider_checks_its_own_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert provider_name() == "openai"  # no Anthropic key: OpenAI
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    assert provider_name() == "anthropic" and make_client().provider == "anthropic"  # the Anthropic key is used first
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert provider_name() == "openai" and has_key() is True and make_client().provider == "openai"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert has_key() is False
    monkeypatch.setenv("LLM_PROVIDER", "nonsense")
    with pytest.raises(LLMError, match="LLM_PROVIDER"):
        provider_name()
