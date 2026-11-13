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
            details = self.validator(upload["file_path"], self.settings.max_frame_gap_seconds)
        except ValueError as exc:
            self.repository.finish_validation(upload_id, False, str(exc))
        except Exception:
            log.exception("Background validation failed for upload %s", upload_id)
            self.repository.finish_validation(upload_id, False, "Background video validation could not complete.")
        else:
            self.repository.finish_validation(upload_id, True, details=details)

    def close(self):
        self.executor.shutdown(wait=True)
