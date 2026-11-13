import logging
from concurrent.futures import ThreadPoolExecutor

from .media import validate_video

log = logging.getLogger(__name__)


class ValidationService:
    def __init__(self, repository, settings, validator=validate_video):
        self.repository, self.settings, self.validator = repository, settings, validator
        self.executor = ThreadPoolExecutor(max_workers=settings.validation_workers, thread_name_prefix="video-preflight")

    def submit(self, upload_id):
        self.executor.submit(self._validate, upload_id)

    def _validate(self, upload_id):
        if not self.repository.start_validation(upload_id):
            return
        upload = self.repository.get_upload(upload_id)
        try:
            if self.validator is validate_video:
                details = self.validator(upload["file_path"], self.settings.max_frame_gap_seconds,
                                         max_duration_seconds=self.settings.max_video_seconds)
            else:
                details = self.validator(upload["file_path"], self.settings.max_frame_gap_seconds)
            if details and details.get("duration_seconds", 0) > self.settings.max_video_seconds:
                raise ValueError(f"Video duration exceeds the {self.settings.max_video_minutes:g}-minute limit.")
        except ValueError as exc:
            self.repository.finish_validation(upload_id, False, str(exc))
        except Exception:
            log.exception("Background validation failed for upload %s", upload_id)
            self.repository.finish_validation(upload_id, False, "Background video validation could not complete.")
        else:
            self.repository.finish_validation(upload_id, True, details=details)

    def close(self):
        self.executor.shutdown(wait=True)
