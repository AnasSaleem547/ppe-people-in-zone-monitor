from pathlib import Path
import shutil

import pytest

from test_repository import add_upload, request


def test_worker_checkpoints_cv_and_retries_upload_without_repeating_inference(video_factory, tmp_path):
    from config import Settings
    from repository import Repository
    from worker import Worker
    repo = Repository(tmp_path / "db.sqlite")
    add_upload(repo, tmp_path, "valid")
    job = repo.create_job(request(), "worker")
    clip = video_factory()
    class Pipeline:
        used = False
        def run(self, path, polygon, n, seconds, output_root):
            if self.used:
                raise AssertionError("CV was repeated after an upload failure")
            self.used = True
            folder = Path(output_root) / "gathering_test"
            folder.mkdir(parents=True)
            shutil.copy(clip, folder / "annotated.mp4")
            return dict(output_dir=str(folder), status="decoder_reached_end", N=n, T=seconds,
                        polygon=polygon, overlap_fraction=.7, events=[dict(seconds=.5, observed=2, estimated=2)], resets=[1.])
    class Storage:
        first = True
        def upload(self, *args):
            from services.cloud_storage import CloudDeliveryError
            if self.first:
                self.first = False
                raise CloudDeliveryError("Temporary delivery failure")
            return dict(video_url="https://res.cloudinary.com/test/video/upload/vc_h264/v1/job.mp4", public_id="job", asset_id="asset", version=1)
    worker = Worker(Settings(_env_file=None, data_dir=tmp_path / "data", retry_delay_seconds=0), repo, Pipeline(), Storage())
    assert worker.run_once() is True
    saved = repo.get_job(job["id"])
    assert saved["status"] == "queued"
    assert "report" in saved["checkpoint"]
    assert Path(saved["checkpoint"]["final_video"]).is_file()
    assert worker.run_once() is True
    finished = repo.get_job(job["id"])
    assert finished["status"] == "succeeded"
    assert finished["attempts"] == 2
    assert finished["result"]["alarm_count"] == 1
    assert finished["result"]["alarms"][0]["start_seconds"] == .5
    assert worker.run_once() is False


def test_process_lock_prevents_two_workers_for_same_data_folder(tmp_path):
    from services.locks import ProcessLock
    with ProcessLock(tmp_path / "worker.lock"):
        with pytest.raises(RuntimeError, match="already running"):
            with ProcessLock(tmp_path / "worker.lock"):
                pass
