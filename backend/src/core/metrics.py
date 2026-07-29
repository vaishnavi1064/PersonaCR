"""
Prometheus metrics for PersonaCR operator observability (dev/portfolio scale).

Live signals come from the same AgentTrace.execution_time_ms values the
dashboard already stores — we observe those into histograms instead of
hand-computing p50/p95 in the API.
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

load_dotenv("backend/.env")

# Optional override for tests (isolated registry).
_registry: CollectorRegistry | None = None

AGENT_LABELS = ("planner", "style", "defect", "qa", "confidence", "orchestrator")

_TRACE_AGENT_MAP = {
    "planner": "planner",
    "style_analyst": "style",
    "defect_hunter": "defect",
    "qa_checker": "qa",
    "confidence_evaluator": "confidence",
    "orchestrator": "orchestrator",
}


def get_registry() -> CollectorRegistry:
    global _registry
    if _registry is None:
        # Default global registry — Prometheus scrapes this process.
        from prometheus_client import REGISTRY

        _registry = REGISTRY
    return _registry


def set_registry(registry: CollectorRegistry | None) -> None:
    """Tests can inject a fresh CollectorRegistry and rebuild metrics."""
    global _registry, REVIEW_LATENCY, REVIEW_TOTAL, SELF_CORRECTION, GROQ_THROTTLED
    _registry = registry
    REVIEW_LATENCY, REVIEW_TOTAL, SELF_CORRECTION, GROQ_THROTTLED = _build_metrics()


def _build_metrics():
    reg = get_registry()
    latency = Histogram(
        "personacr_review_latency_seconds",
        "Per-agent review pipeline latency (from AgentTrace.execution_time_ms)",
        ["agent"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
        registry=reg,
    )
    total = Counter(
        "personacr_review_total",
        "Completed reviews by outcome status",
        ["outcome"],
        registry=reg,
    )
    correction = Counter(
        "personacr_self_correction_total",
        "Agentic self-correction loop outcomes (Loop 1 confidence / Loop 2 quality gate)",
        ["loop", "result"],
        registry=reg,
    )
    throttled = Counter(
        "personacr_groq_throttled_total",
        "Groq rate-limit / throttle hits detected in agent calls",
        registry=reg,
    )
    # Pre-register label combinations so /metrics shows series before first scrape event.
    for agent in AGENT_LABELS:
        latency.labels(agent=agent)
    for outcome in ("passed", "low_confidence", "quality_gate_failed", "failed", "mock_passed"):
        total.labels(outcome=outcome)
    for loop in ("1", "2"):
        for result in ("improved", "reverted", "failed"):
            correction.labels(loop=loop, result=result)
    return latency, total, correction, throttled


REVIEW_LATENCY, REVIEW_TOTAL, SELF_CORRECTION, GROQ_THROTTLED = _build_metrics()


def metrics_enabled() -> bool:
    return os.getenv("PERSONACR_METRICS_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def normalize_agent(agent_name: str) -> str | None:
    return _TRACE_AGENT_MAP.get(agent_name)


def observe_agent_latency_ms(agent: str, execution_time_ms: int | float) -> None:
    """Observe the same millisecond value stored on AgentTrace."""
    if not metrics_enabled():
        return
    label = agent if agent in AGENT_LABELS else normalize_agent(agent)
    if label is None:
        return
    REVIEW_LATENCY.labels(agent=label).observe(max(float(execution_time_ms), 0.0) / 1000.0)


def observe_from_trace(agent_name: str, execution_time_ms: int | float) -> None:
    observe_agent_latency_ms(agent_name, execution_time_ms)


def record_review_outcome(status: str) -> None:
    if not metrics_enabled():
        return
    outcome = (status or "failed").strip() or "failed"
    REVIEW_TOTAL.labels(outcome=outcome).inc()


def record_self_correction(loop: int | str, result: str) -> None:
    if not metrics_enabled():
        return
    SELF_CORRECTION.labels(loop=str(loop), result=result).inc()


def record_groq_throttled() -> None:
    if not metrics_enabled():
        return
    GROQ_THROTTLED.inc()


def maybe_record_groq_throttle(exc: BaseException | str) -> bool:
    """Return True and increment if the error looks like a Groq rate limit."""
    text = str(exc).lower()
    markers = ("rate limit", "rate_limit", "429", "too many requests", "quota")
    if any(m in text for m in markers):
        record_groq_throttled()
        return True
    return False


def record_mock_review(duration_seconds: float) -> None:
    """Synthetic signals for mock/stub reviews (no Groq / no full pipeline)."""
    if not metrics_enabled():
        return
    ms = max(duration_seconds, 0.0) * 1000.0
    observe_agent_latency_ms("orchestrator", ms)
    # Split a token amount across agents so dashboards have series under mock load.
    share = ms / 5.0
    for agent in ("planner", "style", "defect", "qa", "confidence"):
        observe_agent_latency_ms(agent, share)
    record_review_outcome("mock_passed")


@asynccontextmanager
async def track_agent_latency(
    agent: str, *, observe: bool = True
) -> AsyncIterator[None]:
    """
    Async CM for timing an awaitable agent span (correct under asyncio.gather).

    When observe=True, records wall-clock into the histogram. Prefer
    observe=False + observe_from_trace(...) when AgentTrace.execution_time_ms
    is already the canonical timing (dashboard source of truth).
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        if observe:
            observe_agent_latency_ms(agent, (time.perf_counter() - start) * 1000.0)


@contextmanager
def track_agent_latency_sync(agent: str, *, observe: bool = True) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        if observe:
            observe_agent_latency_ms(agent, (time.perf_counter() - start) * 1000.0)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(get_registry()), CONTENT_TYPE_LATEST
