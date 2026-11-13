import threading
import time

import pytest
from fastapi.testclient import TestClient


def payload(upload_id):
    return dict(upload_id=upload_id, n_people=2, threshold_seconds=1,
                polygon=[[0, 0], [159, 0], [159, 119], [0, 119]])


def test_upload_returns_frame_then_job_waits_for_background_validation(video_factory, tmp_path):
    from config import Settings
    from main import create_app
    entered, release = threading.Event(), threading.Event()
    def validator(path, gap):
        entered.set()
        assert release.wait(5)
        from services.media import validate_video
        return validate_video(path, gap)
    app = create_app(Settings(_env_file=None, data_dir=tmp_path / "data"), validator=validator)
    try:
        with TestClient(app) as client:
            response = client.post("/api/uploads", files={"file": ("clip.mp4", video_factory().read_bytes(), "video/mp4")})
            assert response.status_code == 201
            upload = response.json()
            assert upload["first_frame"].startswith("data:image/jpeg;base64,")
            assert upload["width"] == 160
            assert entered.wait(2)
            job = client.post("/api/jobs", json=payload(upload["upload_id"]), headers={"Idempotency-Key": "same"})
            assert job.status_code == 202
            assert job.json()["status"] == "waiting_validation"
            status_url = job.json()["status_url"]
            assert "/v1/" not in status_url
            assert client.get(status_url).json()["region_preview"].startswith("data:image/jpeg;base64,")
            release.set()
            deadline = time.monotonic() + 3
            while client.get(status_url).json()["status"] == "waiting_validation" and time.monotonic() < deadline:
                time.sleep(.01)
            assert client.get(status_url).json()["status"] == "queued"
            assert client.post("/api/jobs", json=payload(upload["upload_id"]), headers={"Idempotency-Key": "same"}).json()["job_id"] == job.json()["job_id"]
            conflict = client.post("/api/jobs", json=dict(payload(upload["upload_id"]), n_people=3), headers={"Idempotency-Key": "same"})
            assert conflict.status_code == 409
    finally:
        release.set()


def test_invalid_video_fails_job_while_waiting(video_factory, tmp_path):
    from config import Settings
    from main import create_app
    release = threading.Event()
    def validator(path, gap):
        release.wait(3)
        raise ValueError("Timestamp gap found.")
    app = create_app(Settings(_env_file=None, data_dir=tmp_path / "data"), validator=validator)
    try:
        with TestClient(app) as client:
            upload = client.post("/api/uploads", files={"file": ("a.mp4", video_factory().read_bytes())}).json()
            job = client.post("/api/jobs", json=payload(upload["upload_id"])).json()
            release.set()
            deadline = time.monotonic() + 2
            while client.get(job["status_url"]).json()["status"] == "waiting_validation" and time.monotonic() < deadline:
                time.sleep(.01)
            result = client.get(job["status_url"]).json()
            assert result["status"] == "failed"
            assert result["error"] == "Timestamp gap found."
            assert result["attempts"] == 0
            assert client.post("/api/jobs", json=payload(upload["upload_id"])).status_code == 422
    finally:
        release.set()


def test_api_rejects_bad_inputs_and_exposes_only_three_application_routes(video_factory, tmp_path):
    from config import Settings
    from main import create_app
    app = create_app(Settings(_env_file=None, data_dir=tmp_path / "data", max_upload_mb=1))
    with TestClient(app) as client:
        assert set(client.get("/openapi.json").json()["paths"]) == {"/api/uploads", "/api/jobs", "/api/jobs/{job_id}"}
        assert client.get("/api/jobs/missing").status_code == 404
        assert client.post("/api/jobs", json=payload("missing")).status_code == 404
        assert client.post("/api/uploads", files={"file": ("a.mp4", b"not-video")}).status_code == 422
        assert client.post("/api/uploads", files={"file": ("a.mp4", b"x" * (1024 * 1024 + 1))}).status_code == 413
        upload = client.post("/api/uploads", files={"file": ("a.mp4", video_factory().read_bytes())}).json()
        for change in ({"n_people": True}, {"n_people": 0}, {"threshold_seconds": 0},
                       {"polygon": [[0, 0], [159, 119], [159, 0], [0, 119]]},
                       {"polygon": [[0, 0], [160, 0], [159, 119], [0, 119]]}):
            assert client.post("/api/jobs", json=dict(payload(upload["upload_id"]), **change)).status_code == 422
