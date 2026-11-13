from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(min_length=1, max_length=128)
    n_people: int = Field(strict=True, ge=1)
    threshold_seconds: FiniteFloat = Field(gt=0)
    polygon: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=4, max_length=4)

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
