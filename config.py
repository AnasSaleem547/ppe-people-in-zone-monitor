"""Infrastructure settings and the notebook's exposed CV defaults."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    data_dir: Path = ROOT / "data"
    api_base_url: str = "http://127.0.0.1:8010"
    environment: Literal["development", "test", "production"] = "development"
    max_upload_mb: int = Field(default=200, ge=1)
    validation_workers: int = Field(default=1, ge=1, le=4)
    worker_poll_seconds: float = Field(default=1, gt=0)
    max_job_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=10, ge=0)
    upload_retention_hours: int = Field(default=24, ge=1)
    short_video_seconds: float = 30
    status_poll_seconds: int = 7
    ffmpeg_path: str = "ffmpeg"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: SecretStr = SecretStr("")
    cloudinary_folder: str = "ppe-monitor"
    cloudinary_timeout_seconds: int = Field(default=120, ge=1)
    model_path: Path = ROOT.parent / "yolo26m.pt"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    image_size: int = Field(default=640, ge=32)
    full_frame_context: bool = False
    overlap_fraction: float = Field(default=.70, gt=0, le=1)
    max_hidden_seconds: float = Field(default=1.5, gt=0)
    max_image_seconds: float = Field(default=2., gt=0)
    max_body_reference_seconds: float = Field(default=2., gt=0)
    max_frame_gap_seconds: float = Field(default=1., gt=0)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    def prepare_directories(self) -> None:
        for name in ("uploads", "jobs"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
