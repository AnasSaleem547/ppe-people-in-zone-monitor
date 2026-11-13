from datetime import datetime, timezone

import pytest


def test_cloud_upload_uses_stable_job_path_and_returns_ready_h264_url(tmp_path, monkeypatch):
    from config import Settings
    from services.cloud_storage import CloudStorage
    import cloudinary.uploader
    import httpx
    captured = {}
    def upload(path, **kwargs):
        captured.update(kwargs)
        return dict(asset_id="asset", public_id=kwargs["public_id"], version=123, resource_type="video",
                    format="mp4", bytes=1024, secure_url="https://res.cloudinary.com/test/video/upload/v123/original.mp4",
                    eager=[dict(transformation="vc_h264", format="mp4", bytes=1024,
                                secure_url=f"https://res.cloudinary.com/test/video/upload/vc_h264/v123/{kwargs['public_id']}.mp4")])
    monkeypatch.setattr(cloudinary.uploader, "upload_large", upload)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, headers={"Content-Type":"video/mp4", "Content-Length":"1024"}))
    settings = Settings(_env_file=None, cloudinary_cloud_name="test", cloudinary_api_key="key", cloudinary_api_secret="secret")
    with httpx.Client(transport=transport) as client:
        result = CloudStorage(settings, http_client=client).upload(tmp_path / "a.mp4", "job123", datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp())
    assert captured["public_id"] == "ppe-monitor/development/2026/11/job123/annotated"
    assert captured["asset_folder"] == "ppe-monitor/development/2026/11/job123"
    assert captured["resource_type"] == "video"
    assert captured["overwrite"] is False
    assert captured["eager_async"] is False
    assert captured["eager"] == [{"video_codec": "h264", "format": "mp4"}]
    assert "/vc_h264/" in result["video_url"]
    assert result["asset_id"] == "asset"


def test_cloud_does_not_report_success_when_delivery_is_unavailable(tmp_path, monkeypatch):
    from config import Settings
    from services.cloud_storage import CloudStorage, CloudDeliveryError
    import cloudinary.uploader
    import httpx
    monkeypatch.setattr(cloudinary.uploader, "upload_large", lambda *a, **kw: dict(asset_id="a", public_id="p", version=1, eager=[dict(secure_url="https://res.cloudinary.com/test/video/upload/vc_h264/v1/p.mp4")]))
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        with pytest.raises(CloudDeliveryError):
            CloudStorage(Settings(_env_file=None, cloudinary_cloud_name="test", cloudinary_api_key="key", cloudinary_api_secret="secret"), http_client=client).upload(tmp_path / "a.mp4", "j", 0)
