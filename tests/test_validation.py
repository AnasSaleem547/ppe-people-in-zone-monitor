def test_validator_persists_decoded_endpoint_for_audio_packaging(video_factory, tmp_path):
    from config import Settings
    from repository import Repository
    from services.media import inspect_video
    from services.validation import ValidationService
    settings = Settings(_env_file=None, data_dir=tmp_path / "data")
    repo = Repository(settings.database_path)
    path = video_factory()
    preview = inspect_video(path)
    preview.pop("jpeg")
    repo.add_upload("u", str(path), "unused.jpg", preview)
    service = ValidationService(repo, settings)
    service.submit("u")
    service.close()
    upload = repo.get_upload("u")
    assert upload["status"] == "valid"
    assert upload["metadata"]["validation"]["duration_seconds"] == 2.5
