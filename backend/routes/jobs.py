import time
import uuid
from urllib.parse import quote
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from backend.database.repository import Conflict
from backend.schemas.jobs import JobRequest, JobResponse
from backend.services.cv.media_utils import validate_polygon
from backend.services.media import image_data_uri, region_preview
from backend.services.progress import job_progress

router = APIRouter(prefix="/api", tags=["Jobs"])


def public_job(request, job):
    repo = request.app.state.repository
    upload = repo.get_upload(job["upload_id"])
    metadata = upload["metadata"]
    marked = region_preview(Path(upload["preview_path"]).read_bytes(), job["request"]["polygon"],
                            metadata["width"], metadata["height"])
    messages = {"waiting_validation": "Waiting for background video validation.",
                "queued": "In queue.", "processing": "Processing started.",
                "adding_audio": "Adding alarm audio.", "uploading": "Uploading the result.",
                "preparing_delivery": "Preparing video playback.", "succeeded": "Processing complete.",
                "failed": "Processing failed."}
    public_id, video_name = repo.public_identity(job)
    return dict(job_id=public_id, job_name=public_id, video_name=video_name, progress=job_progress(job, upload), status=job["status"], phase=job["phase"],
                message=messages.get(job["status"], job["status"]), status_url=f"/api/jobs/{quote(public_id, safe='')}",
                validation_status=upload["status"], queue_position=repo.queue_position(job["id"]),
                duration_seconds=metadata["duration_seconds"],
                attempts=job["attempts"], error=job["error"], region_preview=image_data_uri(marked),
                polygon=job["request"]["polygon"], result=job["result"])


@router.post("/jobs", status_code=202, response_model=JobResponse)
def create_job(request: Request, body: JobRequest,
               idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128)] = None):
    repo = request.app.state.repository
    data = body.model_dump(mode="json")
    existing = repo.get_job_by_key(idempotency_key) if idempotency_key else None
    if existing:
        if existing["request"] != data:
            raise HTTPException(409, "This idempotency key was already used with different inputs.")
        return public_job(request, existing)
    upload = repo.get_upload(body.upload_id)
    if upload is None:
        raise HTTPException(404, "Upload not found.")
    if time.time() - upload["created_at"] > request.app.state.settings.upload_retention_hours * 3600:
        raise HTTPException(410, "Upload has expired. Upload the video again.")
    try:
        validate_polygon(body.polygon, upload["metadata"]["width"], upload["metadata"]["height"])
        job = repo.create_job(data, idempotency_key or uuid.uuid4().hex)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return public_job(request, job)


@router.get("/jobs/{job_id:path}", response_model=JobResponse)
def get_job(request: Request, job_id: str):
    job = request.app.state.repository.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return public_job(request, job)
