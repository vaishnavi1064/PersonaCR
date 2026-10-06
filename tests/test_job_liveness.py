"""
Stuck background jobs: a running job whose worker died must end failed and be
retryable — via the heartbeat staleness check (core/liveness.py) and RQ's
failure hooks (workers/failures.py).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue
from rq.exceptions import AbandonedJobError

from backend.src.core import analysis_store, job_store, liveness
from backend.src.core.redis_client import reset_redis, set_redis
from backend.src.workers import failures

USER = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"
REPO = "https://github.com/acme/api"


@pytest.fixture()
def redis():
    client = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    set_redis(client)
    yield client
    reset_redis()


def _ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _age_job(redis, job_id: str, seconds: float) -> None:
    key = f"{job_store.JOB_KEY_PREFIX}{job_id}"
    data = json.loads(redis.get(key))
    redis.set(key, json.dumps({**data, "updated_at": _ago(seconds)}))


def _age_record(redis, seconds: float) -> None:
    key = analysis_store._key(USER, REPO)
    data = json.loads(redis.get(key))
    redis.set(key, json.dumps({**data, "updated_at": _ago(seconds)}))


def _running_analysis(redis, job_id: str = "job-1", age: float = 0) -> None:
    job_store.create_job(job_id, meta={"kind": "analyze", "repo_url": REPO, "user_id": USER})
    job_store.update_job(job_id, state="running", progress=70, message="Indexing")
    analysis_store.start_record(USER, REPO, job_id, force=True)
    analysis_store.update_record(USER, REPO, state="running", stage="index", progress=70)
    if age:
        _age_job(redis, job_id, age)
        _age_record(redis, age)


# ── the staleness rule ──────────────────────────────────────────────────────

def test_is_stale_only_for_running_without_recent_writes():
    old, fresh = _ago(liveness.STALE_AFTER_SECONDS + 5), _ago(1)
    assert liveness.is_stale({"state": "running", "updated_at": old})
    assert not liveness.is_stale({"state": "running", "updated_at": fresh})
    assert not liveness.is_stale({"state": "queued", "updated_at": old})  # waiting for a worker ≠ dead
    assert not liveness.is_stale({"state": "completed", "updated_at": old})
    assert not liveness.is_stale(None)


# ── reads reconcile dead jobs ───────────────────────────────────────────────

def test_stale_running_job_reads_as_failed(redis):
    _running_analysis(redis, age=liveness.STALE_AFTER_SECONDS + 5)
    job = job_store.get_job("job-1")
    assert job.state == "failed" and job.error == liveness.WORKER_STOPPED


def test_stale_analysis_record_and_its_job_read_as_failed(redis):
    _running_analysis(redis, age=liveness.STALE_AFTER_SECONDS + 5)
    _age_job(redis, "job-1", 1)  # job looks fresh — the record decides, and fails the job too
    rec = analysis_store.get_record(USER, REPO)
    assert rec["state"] == "failed" and rec["error"] == liveness.WORKER_STOPPED and rec["finished_at"]
    assert job_store.get_job("job-1").state == "failed"
    assert analysis_store.list_records(USER)[0]["state"] == "failed"


def test_live_running_job_is_left_alone(redis):
    _running_analysis(redis, age=5)
    assert analysis_store.get_record(USER, REPO)["state"] == "running"
    assert job_store.get_job("job-1").state == "running"


def test_heartbeat_keeps_a_slow_stage_alive(redis):
    _running_analysis(redis, age=liveness.STALE_AFTER_SECONDS - 1)
    job_store.touch("job-1")
    analysis_store.beat(USER, REPO, "job-1")
    time.sleep(1.5)  # past the original deadline, but the beat refreshed it
    assert analysis_store.get_record(USER, REPO)["state"] == "running"
    assert job_store.get_job("job-1").state == "running"


def test_heartbeat_thread_beats_until_exit():
    beats: list[float] = []
    with liveness.Heartbeat(lambda: beats.append(time.monotonic()), interval=0.05):
        time.sleep(0.3)
    n = len(beats)
    time.sleep(0.15)
    assert n >= 3 and len(beats) == n  # beat while running, stopped after


def test_heartbeat_errors_never_fail_the_job():
    def boom():
        raise ConnectionError("redis blip")

    with liveness.Heartbeat(boom, interval=0.02):
        time.sleep(0.1)  # no exception escapes


# ── a replaced job can't write over its replacement ─────────────────────────

def test_old_job_writes_are_ignored_after_a_new_job_starts(redis):
    _running_analysis(redis, job_id="old")
    analysis_store.start_record(USER, REPO, "new", force=True)
    assert analysis_store.update_record(USER, REPO, only_job_id="old", state="completed") is None
    assert analysis_store.get_record(USER, REPO)["job_id"] == "new"
    analysis_store.beat(USER, REPO, "old")
    assert not analysis_store.fail_if_active(USER, REPO, "old", "x")
    assert analysis_store.get_record(USER, REPO)["state"] == "queued"


# ── Reanalyze replaces a dead job ───────────────────────────────────────────

@pytest.fixture()
def client(redis, login, monkeypatch):
    from backend.src.main import app
    from backend.src.routes import analyze_routes

    enqueued: list[str] = []
    monkeypatch.setattr(analyze_routes, "enqueue_analyze_job", lambda job_id, payload: enqueued.append(job_id))
    login(USER)
    with TestClient(app) as c:
        c.enqueued = enqueued  # type: ignore[attr-defined]
        yield c


def test_forced_reanalyze_replaces_a_stale_running_job(client, redis):
    _running_analysis(redis, age=liveness.STALE_AFTER_SECONDS + 5)
    res = client.post("/api/analyze-jobs", json={"repo_url": REPO, "force_refresh": True})
    assert res.status_code == 202
    new_id = res.json()["job_id"]
    assert new_id != "job-1" and client.enqueued == [new_id]
    assert job_store.get_job("job-1").state == "failed"
    assert client.get(f"/api/analyze-jobs/{new_id}").json()["state"] == "queued"


def test_reanalyze_while_live_still_returns_the_running_job(client, redis):
    _running_analysis(redis, age=5)
    res = client.post("/api/analyze-jobs", json={"repo_url": REPO, "force_refresh": True})
    assert res.status_code == 200 and res.json()["job_id"] == "job-1" and client.enqueued == []


def test_polling_a_dead_job_reports_failed(client, redis):
    _running_analysis(redis, age=liveness.STALE_AFTER_SECONDS + 5)
    body = client.get("/api/analyze-jobs/job-1").json()
    assert body["state"] == "failed" and body["error"] == liveness.WORKER_STOPPED
    listed = client.get("/api/repos").json()["repos"]
    assert listed[0]["analysis"]["state"] == "failed"


# ── RQ failure hooks ────────────────────────────────────────────────────────

class _RQJob:
    def __init__(self, job_id: str, payload: dict):
        self.args = (job_id, payload)


def test_abandoned_analyze_job_is_marked_failed(redis):
    _running_analysis(redis)
    failures.on_job_failure(_RQJob("job-1", {"user_id": USER, "repo_url": REPO}), None,
                            AbandonedJobError, AbandonedJobError(), None)
    assert job_store.get_job("job-1").error == liveness.WORKER_STOPPED
    assert analysis_store.get_record(USER, REPO)["state"] == "failed"


def test_killed_work_horse_marks_a_review_job_failed(redis):
    job_store.create_job("rev-1", meta={"kind": "review", "user_id": USER})
    job_store.update_job("rev-1", state="running")
    failures.on_work_horse_killed(_RQJob("rev-1", {"repo_url": REPO, "code": "x"}), 123, 9, None)
    assert job_store.get_job("rev-1").state == "failed"
    assert job_store.get_job("rev-1").error == liveness.WORKER_KILLED


def test_failure_hook_never_overwrites_a_finished_job(redis):
    job_store.create_job("rev-2")
    job_store.update_job("rev-2", state="completed", result={"ok": True})
    failures.on_job_failure(_RQJob("rev-2", {}), None, RuntimeError, RuntimeError("late"), None)
    assert job_store.get_job("rev-2").state == "completed"


def test_jobs_are_enqueued_with_the_failure_callback(redis):
    from backend.src.core import analyze_queue, review_queue

    analyze_queue.enqueue_analyze_job("a1", {"repo_url": REPO, "user_id": USER})
    review_queue.enqueue_review_job("r1", {"repo_url": REPO, "code": "x"})
    for queue_name, job_id in (("analyze", "a1"), ("reviews", "r1")):
        job = Queue(queue_name, connection=redis).fetch_job(job_id)
        assert job.failure_callback is failures.on_job_failure


def test_worker_registers_the_work_horse_killed_handler(monkeypatch):
    from backend.src.workers import worker

    seen: dict = {}

    class FakeWorker:
        def __init__(self, queues, connection, **kwargs):
            seen.update(kwargs)

        def work(self, **kwargs):
            pass

    monkeypatch.setattr(worker, "Worker", FakeWorker)
    monkeypatch.setattr(worker, "WindowsWorker", FakeWorker)
    monkeypatch.setattr(worker.Redis, "from_url", staticmethod(lambda url: fakeredis.FakeStrictRedis()))
    worker.main()
    assert seen["work_horse_killed_handler"] is failures.on_work_horse_killed


# ── a running job beats ─────────────────────────────────────────────────────

def test_analyze_job_beats_while_a_stage_runs(redis, monkeypatch):
    from backend.src.workers import analyze_jobs

    _running_analysis(redis)
    beats: list[str] = []
    monkeypatch.setattr(liveness, "HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(analyze_jobs.job_store, "touch", lambda job_id: beats.append(job_id))
    release = threading.Event()

    def slow_analysis(*a, **k):
        release.wait(0.3)  # a long stage with no progress reports
        raise analyze_jobs.AnalysisError(500, "stop here")

    monkeypatch.setattr(analyze_jobs, "run_analysis", slow_analysis)
    with pytest.raises(analyze_jobs.AnalysisError):
        analyze_jobs.process_analyze_job("job-1", {"user_id": USER, "repo_url": REPO})
    assert beats.count("job-1") >= 3
