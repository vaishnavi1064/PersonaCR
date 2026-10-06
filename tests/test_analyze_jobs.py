"""Background repo analysis: POST /api/analyze-jobs → RQ "analyze" worker → persisted status."""
from __future__ import annotations

from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue, SimpleWorker

from backend.src.core import analysis as analysis_mod
from backend.src.core import analysis_store
from backend.src.core.redis_client import reset_redis, set_redis
from backend.src.routes import repo_routes
from backend.src.workers import analyze_jobs
from tests.conftest import make_chunk

USER = "3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b"
REPO = "https://github.com/acme/api"


@pytest.fixture()
def fake_redis():
    client = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    set_redis(client)
    yield client
    reset_redis()


@pytest.fixture()
def client(fake_redis):
    from backend.src.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pipeline(monkeypatch):
    """Mock GitHub, Chroma and Supabase; record progress callbacks and DB writes."""
    db = MagicMock()
    db.select_many.return_value = []  # user_repos (for GET /api/repos)
    db.select_raw.return_value = []
    monkeypatch.setattr(analysis_mod, "SupabaseREST", lambda: db)
    monkeypatch.setattr(analyze_jobs, "SupabaseREST", lambda: db)
    monkeypatch.setattr(repo_routes, "SupabaseREST", lambda: db)
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(analysis_mod, "embed_and_store", lambda *a, **k: {"collection": "c", "chunks_embedded": 2})
    save_fp = MagicMock()
    monkeypatch.setattr(analysis_mod, "save_fingerprint", save_fp)

    def fake_ingest(url, token=None, on_progress=None):
        for i in range(4):  # like ingest_repo: 0/3 … 3/3
            if on_progress:
                on_progress(i, 3)
        chunks = [make_chunk("f", "def f(x: int) -> int:\n    return x"), make_chunk("g", "def g(y):\n    return y")]
        return chunks, "sha42"

    monkeypatch.setattr(analysis_mod, "ingest_repo", fake_ingest)
    return {"db": db, "save_fingerprint": save_fp}


def drain(fake_redis) -> None:
    SimpleWorker([Queue(analyze_jobs.QUEUE_NAME, connection=fake_redis)], connection=fake_redis).work(burst=True)


def test_job_lifecycle_persists_status_and_adds_repo(client, fake_redis, pipeline, monkeypatch):
    stages: list[str] = []
    real_update = analysis_store.update_record

    def spy(user_id, repo_url, **fields):
        if "message" in fields:
            stages.append(fields["message"])
        return real_update(user_id, repo_url, **fields)

    monkeypatch.setattr(analysis_store, "update_record", spy)
    monkeypatch.setattr(analyze_jobs, "_PROGRESS_INTERVAL_S", 0)

    res = client.post("/api/analyze-jobs", json={"repo_url": REPO + "/", "user_id": USER, "force_refresh": True})
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    assert res.json()["state"] == "queued"

    # Before a worker runs: the repo already shows as queued in the list
    queued = client.get("/api/repos", params={"user_id": USER}).json()["repos"]
    assert queued[0]["repo_url"] == REPO and queued[0]["analysis"]["state"] == "queued"
    assert queued[0]["fingerprint"] is None

    drain(fake_redis)

    job = client.get(f"/api/analyze-jobs/{job_id}").json()
    assert job["state"] == "completed" and job["progress"] == 100
    assert job["result"]["fingerprint"]["type_hint_usage"] == 0.5
    assert job["result"]["cache_status"] == "new"

    # Real stages, in order, including per-file fetch progress
    assert stages[0] == "Starting"
    assert "Fetching files 0/3" in stages and "Fetching files 3/3" in stages
    assert stages.index("Extracting conventions") > stages.index("Fetching files 3/3")
    assert any(s.startswith("Indexing") for s in stages)
    assert stages[-1] == "Done"

    # The worker (not the browser) records the repo in the user's list, and saves the fingerprint
    pipeline["db"].insert.assert_called_once()
    table, row = pipeline["db"].insert.call_args.args
    assert table == "user_repos" and row["user_id"] == USER and row["repo_url"] == REPO and row["functions_count"] == 2
    pipeline["save_fingerprint"].assert_called_once()

    rec = analysis_store.get_record(USER, REPO)
    assert rec["state"] == "completed" and rec["finished_at"] and rec["summary"]["fingerprint"] is None


def test_failure_is_persisted_with_reason(client, fake_redis, pipeline, monkeypatch):
    def boom(*a, **k):
        raise ValueError("Could not access repo acme/api: 404")

    monkeypatch.setattr(analysis_mod, "ingest_repo", boom)
    job_id = client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": USER}).json()["job_id"]
    drain(fake_redis)

    job = client.get(f"/api/analyze-jobs/{job_id}").json()
    assert job["state"] == "failed" and "404" in job["error"]
    listed = client.get("/api/repos", params={"user_id": USER}).json()["repos"]
    assert listed[0]["analysis"]["state"] == "failed"
    assert "404" in listed[0]["analysis"]["error"]
    pipeline["db"].insert.assert_not_called()  # a failed first import isn't added to the list


def test_repeat_request_while_active_returns_same_job(client, fake_redis, pipeline):
    first = client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": USER})
    second = client.post("/api/analyze-jobs", json={"repo_url": REPO + ".git", "user_id": USER})
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert len(Queue(analyze_jobs.QUEUE_NAME, connection=fake_redis)) == 1
    # Once finished, a new request starts a new job
    drain(fake_redis)
    third = client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": USER})
    assert third.status_code == 202 and third.json()["job_id"] != first.json()["job_id"]


def test_other_users_do_not_see_each_others_jobs(client, fake_redis, pipeline):
    client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": USER})
    other = "11111111-2222-4333-8444-555555555555"
    assert client.get("/api/repos", params={"user_id": other}).json()["repos"] == []


def test_queue_offline_is_503_not_a_silent_success(client, pipeline, monkeypatch):
    class Down:
        def __getattr__(self, name):
            def fail(*a, **k):
                raise ConnectionError("redis down")
            return fail

    set_redis(Down())
    res = client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": USER})
    assert res.status_code == 503
    # …and the repo list still loads (no analysis status)
    assert client.get("/api/repos", params={"user_id": USER}).status_code == 200


def test_guest_analysis_lists_from_its_record(client, fake_redis, pipeline):
    guest = "guest_abc"
    client.post("/api/analyze-jobs", json={"repo_url": REPO, "user_id": guest})
    drain(fake_redis)
    repos = client.get("/api/repos", params={"user_id": guest}).json()["repos"]
    assert len(repos) == 1
    assert repos[0]["analysis"]["state"] == "completed"
    assert repos[0]["fingerprint"]["type_hint_usage"] == 0.5  # kept with the record — not in the DB
    pipeline["save_fingerprint"].assert_not_called()
    pipeline["db"].insert.assert_not_called()


def test_bad_url_is_400(client, fake_redis, pipeline):
    assert client.post("/api/analyze-jobs", json={"repo_url": "not-a-repo", "user_id": USER}).status_code == 400


def test_unknown_job_is_404(client, fake_redis):
    assert client.get("/api/analyze-jobs/nope").status_code == 404


def test_sync_route_still_works(client, fake_redis, pipeline):
    res = client.post("/api/analyze-repo", json={"repo_url": REPO, "user_id": USER, "force_refresh": True})
    assert res.status_code == 200 and res.json()["num_functions"] == 2


def test_worker_listens_to_both_queues():
    import inspect

    from backend.src.workers import worker

    src = inspect.getsource(worker.main)
    assert "REVIEW_QUEUE" in src and "ANALYZE_QUEUE" in src
    assert worker.WindowsWorker.death_penalty_class.__name__ == "TimerDeathPenalty"
