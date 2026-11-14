"""Single local worker: python -m backend.workers.worker. No Celery/Redis dependency."""
import logging
import signal
import time
from pathlib import Path

from backend.core.config import Settings
from backend.core import config as cfg
from backend.database.repository import Repository
from backend.services.alarms import add_alarm_audio, build_intervals
from backend.services.cloud_storage import CloudDeliveryError, CloudStorage
from backend.services.locks import ProcessLock
from backend.services.media import video_endpoint
from backend.services.pipeline import PipelineRunner
from backend.services.model_assets import ensure_model

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings, repository=None, pipeline=None, storage=None):
        self.settings = settings
        settings.prepare_directories()
        self.repository = repository or Repository(settings.database_path)
        self.pipeline = pipeline or PipelineRunner(settings)
        self.storage = storage or CloudStorage(settings)

    def run_once(self):
        repo = self.repository
        job = repo.claim_job()
        if job is None:
            return False
        job_id, body, checkpoint = job["id"], job["request"], job["checkpoint"]
        root = self.settings.data_dir / "jobs" / job_id
        root.mkdir(parents=True, exist_ok=True)
        try:
            upload = repo.get_upload(job["upload_id"])
            if "report" not in checkpoint:
                attempt_root = root / f"attempt-{job['attempts']}"
                checkpoint["cv_root"] = str(attempt_root)
                repo.update_job(job_id, checkpoint=checkpoint)
                report = self.pipeline.run(upload["file_path"], body["polygon"], body["n_people"],
                                           body["threshold_seconds"], attempt_root,
                                           zone_policy=checkpoint.get("zone_policy") or dict(mode="box_overlap",overlap_fraction=cfg.LEGACY_ZONE_OVERLAP_FRACTION))
                if report["status"] != "decoder_reached_end":
                    raise RuntimeError("The CV pipeline did not finish decoding the recording.")
                checkpoint["report"] = report
                repo.update_job(job_id, checkpoint=checkpoint)
            report = checkpoint["report"]
            annotated = Path(report["output_dir"]) / "annotated.mp4"
            endpoint = max(video_endpoint(annotated), upload["metadata"].get("validation", {}).get("duration_seconds", 0))
            intervals = build_intervals(report, endpoint)
            if "final_video" not in checkpoint:
                repo.update_job(job_id, status="adding_audio", phase="adding_audio")
                final = add_alarm_audio(annotated, root / "annotated-with-alarm.mp4", intervals,
                                        endpoint, self.settings.ffmpeg_path)
                checkpoint["final_video"] = str(final)
                repo.update_job(job_id, checkpoint=checkpoint)
            repo.update_job(job_id, status="uploading", phase="uploading")
            delivery = self.storage.upload(checkpoint["final_video"], job_id, job["created_at"])
            result = dict(**delivery, alarm_count=len(intervals), alarms=intervals,
                          n_people=report["N"], threshold_seconds=report["T"], polygon=report["polygon"],
                          overlap_fraction=report["overlap_fraction"], duration_seconds=endpoint,
                          zone_policy=report.get("zone_policy") or checkpoint.get("zone_policy") or dict(mode="box_overlap",overlap_fraction=report["overlap_fraction"]),
                          timer_policy="estimated_continuity_confirm_alarm_with_direct_detections")
            repo.update_job(job_id, status="succeeded", phase="complete", result=result, error=None)
        except CloudDeliveryError as exc:
            retry = job["attempts"] < self.settings.max_job_attempts
            repo.update_job(job_id, status="queued" if retry else "failed", phase="upload_retry" if retry else "uploading",
                            error=str(exc), retry_at=time.time() + self.settings.retry_delay_seconds)
            log.warning("Job %s cloud delivery %s (attempt %s)", job_id, "will retry" if retry else "failed", job["attempts"])
        except Exception:
            log.exception("Job %s failed", job_id)
            repo.update_job(job_id, status="failed", phase="processing_error",
                            error="Processing failed. See the local worker log and this job's saved outputs.")
        return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    with ProcessLock(settings.data_dir / "worker.lock"):
        ensure_model(settings)
        worker = Worker(settings)
        worker.repository.recover_jobs()
        stopped = False
        def stop(signum, frame):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        log.info("Worker ready; one video at a time.")
        while not stopped:
            if not worker.run_once():
                time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
