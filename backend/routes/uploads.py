import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.schemas.jobs import UploadResponse
from backend.services.media import image_data_uri, inspect_video

router = APIRouter(prefix="/api", tags=["Uploads"])


@router.post("/uploads", status_code=201, response_model=UploadResponse)
async def upload_video(request: Request, file: UploadFile):
    settings = request.app.state.settings
    upload_id = uuid.uuid4().hex
    folder = settings.data_dir / "uploads" / upload_id
    folder.mkdir(parents=True)
    path, preview_path = folder / "source.video", folder / "first-frame.jpg"
    size = 0
    try:
        with path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_mb * 1024 * 1024:
                    raise HTTPException(413, f"Video exceeds the {settings.max_upload_mb} MB upload limit.")
                target.write(chunk)
        preview = await run_in_threadpool(inspect_video, path)
        if preview["duration_seconds"] is not None and preview["duration_seconds"] > settings.max_video_seconds:
            raise ValueError(f"Video duration exceeds the {settings.max_video_minutes:g}-minute limit.")
        jpeg = preview.pop("jpeg")
        preview["filename"] = Path((file.filename or "video").replace("\\", "/")).name
        preview_path.write_bytes(jpeg)
        request.app.state.repository.add_upload(upload_id, str(path), str(preview_path), preview)
    except (ValueError, HTTPException) as exc:
        path.unlink(missing_ok=True)
        preview_path.unlink(missing_ok=True)
        folder.rmdir()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
    request.app.state.validation.submit(upload_id)
    return dict(upload_id=upload_id, first_frame=image_data_uri(jpeg),
                validation_status="pending", **{k: v for k, v in preview.items() if k not in ("first_timestamp", "filename")})
