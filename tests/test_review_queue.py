"""Async review queue — mock success/failure lifecycle (no Groq)."""
from __future__ import annotations

import uuid

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue, SimpleWorker

from backend.src.core import job_store
from backend.src.core.redis_client import reset_redis, set_redis
from backend.src.core.review_queue import enqueue_review_job, get_reviews_queue
from backend.src.workers.review_jobs import QUEUE_NAME, process_review_job


@pytest.fixture()
def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server)
    set_redis(client)
    yield client
    reset_redis()


@pytest.fixture()
def client(fake_redis):
    from backend.src.main import app

    with TestClient(app) as c:
        yield c


def _drain_queue(fake_redis) -> None:
    q = Queue(QUEUE_NAME, connection=fake_redis)
    worker = SimpleWorker([q], connection=fake_redis)
    worker.work(burst=True)


def test_mock_job_success_lifecycle(client, fake_redis):
    resp = client.post(
        "/api/reviews",
        json={
            "repo_url": "https://github.com/acme/demo",
            "code": "def hello():\n    return 1\n",
            "language": "python",
            "mock": True,
            "mock_sleep": 0.05,
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    job_id = body["job_id"]
    assert body["state"] == "queued"
    assert body["progress"] == 0

    # Immediate GET while still queued
    queued = client.get(f"/api/reviews/{job_id}")
    assert queued.status_code == 200
    assert queued.json()["state"] == "queued"

    _drain_queue(fake_redis)

    done = client.get(f"/api/reviews/{job_id}")
    assert done.status_code == 200
    data = done.json()
    assert data["state"] == "completed"
    assert data["progress"] == 100
    assert data["error"] is None
    assert data["result"]["overall_score"] == 88.0
    assert data["result"]["review_output"]["mock"] is True
    assert data["review_id"]

    report = client.get(f"/api/reviews/{job_id}/report")
    assert report.status_code == 200
    assert report.json()["status"] == "completed"
    assert report.json()["report"]["overall_score"] == 88.0


def test_mock_job_failure_sets_failed(client, fake_redis):
    resp = client.post(
        "/api/reviews",
        json={
            "repo_url": "https://github.com/acme/demo",
            "code": "def boom():\n    pass\n",
            "mock": True,
            "force_fail": True,
        },
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    _drain_queue(fake_redis)

    failed = client.get(f"/api/reviews/{job_id}")
    assert failed.status_code == 200
    data = failed.json()
    assert data["state"] == "failed"
    assert data["progress"] == 100
    assert data["error"]
    assert "Forced mock failure" in data["error"]
    assert data["result"] is None

    report = client.get(f"/api/reviews/{job_id}/report")
    assert report.status_code == 409


def test_process_review_job_direct_success(fake_redis):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id)
    result = process_review_job(
        job_id,
        {
            "repo_url": "https://github.com/acme/demo",
            "code": "x = 1",
            "language": "python",
            "mock": True,
            "mock_sleep": 0.01,
        },
    )
    assert result["overall_score"] == 88.0
    status = job_store.get_job(job_id)
    assert status is not None
    assert status.state == "completed"


def test_process_review_job_direct_failure(fake_redis):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id)
    with pytest.raises(RuntimeError, match="Forced mock failure"):
        process_review_job(
            job_id,
            {
                "repo_url": "https://github.com/acme/demo",
                "code": "x = 1",
                "mock": True,
                "force_fail": True,
            },
        )
    status = job_store.get_job(job_id)
    assert status is not None
    assert status.state == "failed"
    assert status.error is not None


def test_unknown_job_404(client, fake_redis):
    resp = client.get(f"/api/reviews/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_enqueue_helper_uses_queue(fake_redis):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id)
    rq_id = enqueue_review_job(
        job_id,
        {
            "repo_url": "https://github.com/acme/demo",
            "code": "x=1",
            "mock": True,
            "mock_sleep": 0.01,
        },
    )
    assert rq_id == job_id
    q = get_reviews_queue()
    assert q.count == 1
    _drain_queue(fake_redis)
    assert job_store.get_job(job_id).state == "completed"
