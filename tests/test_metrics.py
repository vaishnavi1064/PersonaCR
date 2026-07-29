"""Prometheus /metrics export — no Groq, no Docker required."""
from __future__ import annotations

import re
import uuid

import fakeredis
import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from rq import Queue, SimpleWorker

from backend.src.core import job_store
from backend.src.core.metrics import (
    maybe_record_groq_throttle,
    record_mock_review,
    record_self_correction,
    render_metrics,
    set_registry,
)
from backend.src.core.redis_client import reset_redis, set_redis
from backend.src.workers.review_jobs import QUEUE_NAME, process_review_job


@pytest.fixture()
def metrics_registry():
    reg = CollectorRegistry()
    set_registry(reg)
    yield reg


@pytest.fixture()
def fake_redis():
    client = fakeredis.FakeStrictRedis()
    set_redis(client)
    yield client
    reset_redis()


@pytest.fixture()
def client(metrics_registry):
    from backend.src.main import app

    with TestClient(app) as c:
        yield c


def _metric_value(body: str, name: str, labels: str | None = None) -> float | None:
    """Parse a single Prometheus sample value from text exposition."""
    if labels:
        pat = rf"^{re.escape(name)}\{{{re.escape(labels)}\}} ([0-9.eE+-]+)"
    else:
        pat = rf"^{re.escape(name)} ([0-9.eE+-]+)"
    m = re.search(pat, body, re.MULTILINE)
    return float(m.group(1)) if m else None


def test_metrics_endpoint_exposes_personacr_series(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    body = resp.text
    assert "personacr_review_latency_seconds" in body
    assert "personacr_review_total" in body
    assert "personacr_self_correction_total" in body
    assert "personacr_groq_throttled_total" in body
    for agent in ("planner", "style", "defect", "qa", "confidence", "orchestrator"):
        assert f'agent="{agent}"' in body


def test_mock_review_increments_counters(client, metrics_registry, fake_redis):
    before = client.get("/metrics").text
    before_total = _metric_value(
        before, "personacr_review_total", 'outcome="mock_passed"'
    ) or 0.0

    resp = client.post(
        "/api/reviews",
        json={
            "repo_url": "https://github.com/acme/demo",
            "code": "def hello():\n    return 1\n",
            "mock": True,
            "mock_sleep": 0.02,
        },
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    q = Queue(QUEUE_NAME, connection=fake_redis)
    SimpleWorker([q], connection=fake_redis).work(burst=True)

    status = job_store.get_job(job_id)
    assert status is not None and status.state == "completed"

    after = client.get("/metrics").text
    after_total = _metric_value(
        after, "personacr_review_total", 'outcome="mock_passed"'
    )
    assert after_total is not None
    assert after_total >= before_total + 1.0
    assert "personacr_review_latency_seconds_count" in after
    assert 'agent="orchestrator"' in after


def test_direct_mock_and_throttle_helpers(metrics_registry):
    record_mock_review(0.05)
    record_self_correction(2, "reverted")
    assert maybe_record_groq_throttle("Error 429 rate_limit exceeded") is True

    body = render_metrics()[0].decode("utf-8")
    assert (_metric_value(body, "personacr_review_total", 'outcome="mock_passed"') or 0) >= 1
    assert (
        _metric_value(
            body, "personacr_self_correction_total", 'loop="2",result="reverted"'
        )
        or 0
    ) >= 1
    assert (_metric_value(body, "personacr_groq_throttled_total") or 0) >= 1


def test_process_review_job_records_mock_metrics(metrics_registry, fake_redis):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id)
    process_review_job(
        job_id,
        {
            "repo_url": "https://github.com/acme/demo",
            "code": "x=1",
            "mock": True,
            "mock_sleep": 0.01,
        },
    )
    body = render_metrics()[0].decode("utf-8")
    assert (_metric_value(body, "personacr_review_total", 'outcome="mock_passed"') or 0) >= 1
