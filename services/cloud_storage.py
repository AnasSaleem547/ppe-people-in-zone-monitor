"""Stable Cloudinary asset names and synchronous H.264 delivery preparation."""
from datetime import datetime, timezone
from urllib.parse import urlparse

import cloudinary.uploader
import httpx


class CloudDeliveryError(RuntimeError):
    pass


class CloudStorage:
    def __init__(self, settings, http_client=None):
        self.settings = settings
        self.http_client = http_client

    def upload(self, path, job_id, created_at):
        s = self.settings
        if not (s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret.get_secret_value()):
            raise CloudDeliveryError("Cloudinary credentials are missing from the backend environment.")
        date = datetime.fromtimestamp(created_at, timezone.utc)
        folder = f"{s.cloudinary_folder}/{date:%Y/%m}/{job_id}"
        public_id = f"{folder}/annotated"
        credentials = dict(cloud_name=s.cloudinary_cloud_name, api_key=s.cloudinary_api_key,
                           api_secret=s.cloudinary_api_secret.get_secret_value())
        eager = [{"video_codec": "h264", "format": "mp4"}]
        try:
            response = cloudinary.uploader.upload_large(
                str(path), resource_type="video", public_id=public_id, asset_folder=folder,
                overwrite=False, unique_filename=False, eager=eager, eager_async=False,
                chunk_size=6 * 1024 * 1024, timeout=s.cloudinary_timeout_seconds,
                tags=["ppe-monitor"], **credentials,
            )
            # overwrite=False may return an existing asset after a lost response.
            # Explicit preparation also obtains its ready derived delivery URL.
            if not response.get("eager"):
                response = cloudinary.uploader.explicit(public_id, resource_type="video", type="upload",
                    eager=eager, eager_async=False, timeout=s.cloudinary_timeout_seconds, **credentials)
            derived = response["eager"][0]
            url = derived.get("secure_url")
            parsed = urlparse(url or "")
            if (parsed.scheme != "https" or parsed.hostname != "res.cloudinary.com"
                    or "vc_h264" not in parsed.path or not parsed.path.endswith(".mp4")
                    or derived.get("status") in ("pending", "failed")):
                raise CloudDeliveryError("Cloudinary did not return a ready H.264 MP4 URL.")
            def verify(client):
                delivery = client.head(url, timeout=s.cloudinary_timeout_seconds, follow_redirects=True)
                delivery.raise_for_status()
                if "video/" not in delivery.headers.get("content-type", ""):
                    raise CloudDeliveryError("Cloudinary delivery did not return video content.")
            if self.http_client is not None:
                verify(self.http_client)
            else:
                with httpx.Client() as client:
                    verify(client)
            return dict(video_url=url, asset_id=response["asset_id"],
                        public_id=response["public_id"], version=response["version"])
        except CloudDeliveryError:
            raise
        except Exception as exc:
            # Credentials and provider request signatures never reach API errors.
            raise CloudDeliveryError("Cloudinary upload or video delivery preparation failed.") from exc
