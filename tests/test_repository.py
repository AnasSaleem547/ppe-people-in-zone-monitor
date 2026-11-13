from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def add_upload(repo, tmp_path, state="pending"):
    path = tmp_path / "source.mp4"
    path.write_bytes(b"video")
    repo.add_upload("u1", str(path), str(path.with_suffix(".jpg")),
                    dict(width=160, height=120, preview_width=160, preview_height=120,
                         duration_seconds=2.5, first_timestamp=0))
    if state != "pending":
        repo.finish_validation("u1", state == "valid", "bad video" if state == "invalid" else None)


def request():
    return dict(upload_id="u1", n_people=2, threshold_seconds=1,
                polygon=[[0, 0], [159, 0], [159, 119], [0, 119]])


def test_waiting_jobs_only_become_claimable_after_successful_validation(tmp_path):
    from repository import Repository
    repo = Repository(tmp_path / "queue.db")
    add_upload(repo, tmp_path)
    job = repo.create_job(request(), "key-a")
    assert job["status"] == "waiting_validation"
    assert repo.claim_job() is None
    repo.finish_validation("u1", True)
    job = Repository(tmp_path / "queue.db").claim_job()
    assert job["status"] == "processing"
    assert job["attempts"] == 1


def test_validation_failure_fails_waiting_jobs_without_inference(tmp_path):
    from repository import Repository
    repo = Repository(tmp_path / "queue.db")
    add_upload(repo, tmp_path)
    job = repo.create_job(request(), "key-a")
    repo.finish_validation("u1", False, "Timestamp gap")
    assert repo.get_job(job["id"])["status"] == "failed"
    assert repo.get_job(job["id"])["error"] == "Timestamp gap"
    assert repo.claim_job() is None
    with pytest.raises(ValueError, match="Timestamp gap"):
        repo.create_job(request(), "key-b")


def test_retry_key_reuses_job_but_rejects_different_inputs(tmp_path):
    from repository import Repository, Conflict
    repo = Repository(tmp_path / "queue.db")
    add_upload(repo, tmp_path, "valid")
    a = repo.create_job(request(), "same")
    assert repo.create_job(request(), "same")["id"] == a["id"]
    with pytest.raises(Conflict):
        repo.create_job(dict(request(), n_people=3), "same")


def test_job_claim_is_atomic_across_connections(tmp_path):
    from repository import Repository
    repo = Repository(tmp_path / "queue.db")
    add_upload(repo, tmp_path, "valid")
    repo.create_job(request(), "same")
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: Repository(tmp_path / "queue.db").claim_job(), range(4)))
    assert len([x for x in claimed if x is not None]) == 1


def test_recovery_requeues_interrupted_jobs_and_keeps_checkpoints(tmp_path):
    from repository import Repository
    repo = Repository(tmp_path / "queue.db")
    add_upload(repo, tmp_path, "valid")
    j = repo.create_job(request(), "a")
    repo.claim_job()
    repo.update_job(j["id"], status="uploading", checkpoint={"annotated": "retained.mp4"})
    repo.recover_jobs()
    recovered = repo.claim_job()
    assert recovered["id"] == j["id"]
    assert recovered["checkpoint"] == {"annotated": "retained.mp4"}
