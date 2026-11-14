from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator

from backend.core import config as cfg


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(min_length=cfg.API_ID_MIN_LENGTH, max_length=cfg.API_ID_MAX_LENGTH)
    n_people: int = Field(strict=True, ge=cfg.JOB_MIN_PEOPLE)
    threshold_seconds: FiniteFloat = Field(gt=cfg.JOB_MIN_THRESHOLD_SECONDS)
    polygon: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=cfg.JOB_POLYGON_POINT_COUNT, max_length=cfg.JOB_POLYGON_POINT_COUNT)

    @field_validator("threshold_seconds", mode="before")
    @classmethod
    def reject_boolean_seconds(cls, value):
        if isinstance(value, bool):
            raise ValueError("T must be a positive number of video seconds.")
        return value


class UploadResponse(BaseModel):
    upload_id: str
    first_frame: str
    width: int
    height: int
    preview_width: int
    preview_height: int
    duration_seconds: float | None
    validation_status: str


class JobResponse(BaseModel):
    zone_policy: dict = Field(default_factory=dict)
    job_name: str = "Video"
    progress: dict = Field(default_factory=dict)
    video_name: str = "Video"
    job_id: str
    status: str
    phase: str
    message: str
    status_url: str
    validation_status: str
    duration_seconds: float | None = None
    queue_position: int | None = None
    attempts: int
    error: str | None = None
    region_preview: str
    polygon: list[list[float]]
    result: dict | None = None
