"""core.llm_client — provider selection, Anthropic request shape, token logging, typed failures."""
from __future__ import annotations

import inspect
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx2
import pytest

import backend.src.core.llm_client as llm


def _message(blocks, stop="end_turn", in_tok=120, out_tok=45):
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _text(t):
    return SimpleNamespace(type="text", text=t)


_REAL_CREATE = inspect.signature(anthropic.resources.messages.Messages.create)


def _check_real_signature(*args, **kwargs):
    """Fail like the real SDK would on an unknown keyword (MagicMock accepts anything)."""
    _REAL_CREATE.bind(None, **kwargs)  # raises TypeError on e.g. temperature=


@pytest.fixture
def fake_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = MagicMock()
    client.messages.create.side_effect = lambda **kw: (_check_real_signature(**kw), client._reply)[1]
    monkeypatch.setattr(llm, "_clients", {"anthropic": client})
    return client


def _status_error(cls, code):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(f"HTTP {code}", response=httpx2.Response(code, request=req), body=None)


def test_defaults_are_anthropic_haiku(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.provider() == "anthropic"
    assert llm.model() == "claude-haiku-4-5-20251001"


def test_env_overrides_and_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "some/model")
    assert (llm.provider(), llm.model()) == ("groq", "some/model")
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError):
        llm.provider()


def test_anthropic_request_shape_and_text_join(fake_anthropic, caplog):
    fake_anthropic._reply = _message(
        [SimpleNamespace(type="thinking", thinking=""), _text('{"a": '), _text("1}")]
    )
    with caplog.at_level(logging.INFO, logger="backend.src.core.llm_client"):
        out = llm.complete("SYS", "USER", temperature=0.1, max_tokens=800, caller="qa")

    assert out == '{"a": 1}'  # text blocks only, in order
    kwargs = fake_anthropic.messages.create.call_args.kwargs
    assert kwargs["system"] == "SYS"  # system is a separate param, not a message
    assert kwargs["messages"] == [{"role": "user", "content": "USER"}]
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["max_tokens"] == 800
    assert "temperature" not in kwargs  # removed from SDK 1.x signature
    assert kwargs["extra_body"] == {"temperature": 0.1}  # Haiku 4.5 accepts it via the body
    assert any("caller=qa input_tokens=120 output_tokens=45" in r.message for r in caplog.records)


@pytest.mark.parametrize("model_id", ["claude-sonnet-5", "claude-opus-5", "claude-opus-4-8"])
def test_temperature_omitted_for_models_that_reject_sampling(fake_anthropic, monkeypatch, model_id):
    monkeypatch.setenv("LLM_MODEL", model_id)
    fake_anthropic._reply = _message([_text("ok")])
    llm.complete("s", "u", temperature=0.2, max_tokens=100)
    kwargs = fake_anthropic.messages.create.call_args.kwargs
    assert "temperature" not in kwargs and "extra_body" not in kwargs


@pytest.mark.parametrize(
    "exc, kind",
    [
        (_status_error(anthropic.NotFoundError, 404), "not_found"),
        (_status_error(anthropic.RateLimitError, 429), "rate_limit"),
        (_status_error(anthropic.AuthenticationError, 401), "auth"),
        (_status_error(anthropic.BadRequestError, 400), "bad_request"),
        (_status_error(anthropic.InternalServerError, 500), "api"),
    ],
)
def test_api_errors_raise_typed_llm_error(fake_anthropic, exc, kind):
    fake_anthropic.messages.create.side_effect = exc
    with pytest.raises(llm.LLMError) as ei:
        llm.complete("s", "u")
    assert ei.value.kind == kind and ei.value.provider == "anthropic"


def test_refusal_and_empty_responses_raise(fake_anthropic):
    fake_anthropic._reply = _message([], stop="refusal")
    with pytest.raises(llm.LLMError, match="refusal"):
        llm.complete("s", "u")
    fake_anthropic._reply = _message([_text("   ")])
    with pytest.raises(llm.LLMError) as ei:
        llm.complete("s", "u")
    assert ei.value.kind == "empty"


def test_groq_provider_path(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2),
    )
    monkeypatch.setattr(llm, "_clients", {"groq": client})

    assert llm.complete("s", "u", temperature=0.3, max_tokens=50) == "hi"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-oss-120b"
    assert kwargs["messages"][0] == {"role": "system", "content": "s"}


def test_unexpected_client_exception_is_wrapped_and_tracked(fake_anthropic):
    fake_anthropic.messages.create.side_effect = TypeError("got an unexpected keyword argument 'x'")
    with llm.track() as t, pytest.raises(llm.LLMError) as ei:
        llm.complete("s", "u", caller="defect")
    assert ei.value.kind == "client"
    assert t.failures and t.failures[0]["caller"] == "defect" and t.failures[0]["kind"] == "client"
