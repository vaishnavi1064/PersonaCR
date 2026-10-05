"""
LLM client — the single entry point every agent uses for a completion.

    complete(system, user, temperature, max_tokens) -> str

Provider and model come from the environment:

    LLM_PROVIDER   "anthropic" (default) | "groq"
    LLM_MODEL      default per provider (see DEFAULT_MODELS)
    ANTHROPIC_API_KEY / GROQ_API_KEY   read by the provider SDKs

Anthropic default is Claude Haiku 4.5 (cheap, for testing). Deployments set
LLM_MODEL to a Sonnet-class model (see README / k8s/README.md).

Every call logs provider, model, caller, input/output tokens and latency.
Failures raise LLMError — callers must not treat a failed call as a result.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    # llama-3.3-70b-versatile was retired by Groq; gpt-oss-120b is in Groq's catalog.
    "groq": "openai/gpt-oss-120b",
}

# Claude models that reject sampling params (temperature/top_p/top_k → HTTP 400):
# Sonnet 5, Opus 5 / 5.5 / 4.7 / 4.8, Fable / Mythos. Haiku 4.5, Sonnet 4.6, Opus 4.6
# and older accept temperature.
_NO_SAMPLING_PREFIXES = (
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-fable",
    "claude-mythos",
)


class LLMError(RuntimeError):
    """An LLM call failed. ``kind`` is a stable short label for status/metrics."""

    def __init__(self, message: str, *, provider: str, model: str, kind: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.kind = kind  # not_found | rate_limit | auth | bad_request | api | connection | empty | refusal


@dataclass
class LLMUsage:
    """Process-wide running totals (thread-safe); per-call numbers are logged."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failures: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens

    def fail(self) -> None:
        with self._lock:
            self.failures += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "failures": self.failures,
            }


usage = LLMUsage()

_clients: dict[str, Any] = {}
_clients_lock = threading.Lock()


def provider() -> str:
    p = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
    if p not in DEFAULT_MODELS:
        raise ValueError(f"Unsupported LLM_PROVIDER={p!r} (expected one of {sorted(DEFAULT_MODELS)})")
    return p


def model() -> str:
    return os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS[provider()]


def accepts_temperature(model_id: str) -> bool:
    return not model_id.startswith(_NO_SAMPLING_PREFIXES)


def _client(name: str) -> Any:
    with _clients_lock:
        if name not in _clients:
            if name == "anthropic":
                import anthropic

                _clients[name] = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
            else:
                from groq import Groq

                _clients[name] = Groq()  # GROQ_API_KEY from env
        return _clients[name]


def complete(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    *,
    caller: str = "unknown",
) -> str:
    """Return the model's text for one system + user turn. Raises LLMError on failure."""
    prov, mdl = provider(), model()
    t0 = time.perf_counter()
    try:
        if prov == "anthropic":
            text, in_tok, out_tok, stop = _complete_anthropic(mdl, system, user, temperature, max_tokens)
        else:
            text, in_tok, out_tok, stop = _complete_groq(mdl, system, user, temperature, max_tokens)
    except LLMError:
        usage.fail()
        raise
    ms = (time.perf_counter() - t0) * 1000.0
    usage.add(in_tok, out_tok)
    logger.info(
        "LLM call provider=%s model=%s caller=%s input_tokens=%d output_tokens=%d stop=%s ms=%.0f",
        prov, mdl, caller, in_tok, out_tok, stop, ms,
    )
    if stop in ("max_tokens", "length"):
        logger.warning("LLM output truncated at max_tokens=%d (caller=%s)", max_tokens, caller)
    if not text.strip():
        usage.fail()
        raise LLMError(f"Empty response from {prov}/{mdl}", provider=prov, model=mdl, kind="empty")
    return text


def _complete_anthropic(
    mdl: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int, str | None]:
    import anthropic

    params: dict[str, Any] = {
        "model": mdl,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if accepts_temperature(mdl):
        params["temperature"] = temperature
    try:
        resp = _client("anthropic").messages.create(**params)
    except anthropic.NotFoundError as e:
        raise LLMError(f"Anthropic model not found ({mdl}): {e}", provider="anthropic", model=mdl, kind="not_found") from e
    except anthropic.RateLimitError as e:
        _record_throttle()
        raise LLMError(f"Anthropic rate limit: {e}", provider="anthropic", model=mdl, kind="rate_limit") from e
    except anthropic.AuthenticationError as e:
        raise LLMError(f"Anthropic auth failed: {e}", provider="anthropic", model=mdl, kind="auth") from e
    except anthropic.BadRequestError as e:
        raise LLMError(f"Anthropic bad request: {e}", provider="anthropic", model=mdl, kind="bad_request") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error {e.status_code}: {e}", provider="anthropic", model=mdl, kind="api") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"Anthropic connection error: {e}", provider="anthropic", model=mdl, kind="connection") from e

    if resp.stop_reason == "refusal":
        raise LLMError("Anthropic declined the request (stop_reason=refusal)", provider="anthropic", model=mdl, kind="refusal")
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason


def _complete_groq(
    mdl: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int, str | None]:
    try:
        resp = _client("groq").chat.completions.create(
            model=mdl,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:  # groq SDK error classes vary by version
        status = getattr(e, "status_code", None)
        kind = {404: "not_found", 429: "rate_limit", 401: "auth", 400: "bad_request"}.get(status or 0, "api")
        if kind == "rate_limit":
            _record_throttle()
        raise LLMError(f"Groq error ({status}): {e}", provider="groq", model=mdl, kind=kind) from e
    choice = resp.choices[0]
    u = getattr(resp, "usage", None)
    return (
        choice.message.content or "",
        getattr(u, "prompt_tokens", 0) or 0,
        getattr(u, "completion_tokens", 0) or 0,
        choice.finish_reason,
    )


def _record_throttle() -> None:
    # Metric name kept for the existing Grafana panel; counts throttles from any provider.
    from backend.src.core.metrics import record_groq_throttled

    record_groq_throttled()
