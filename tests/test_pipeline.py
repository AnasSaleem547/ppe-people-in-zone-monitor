from pathlib import Path


def test_adapter_runs_real_pipeline_with_notebook_flags(video_factory, tmp_path):
    from config import Settings
    from services.pipeline import PipelineRunner

    class RecordedDetector:
        weights = "recorded"
        device = "cpu"
        image_size = 640
        def predict(self, image):
            return [{"xyxy": [30, 10, 80, 105], "score": .95}]

    runner = PipelineRunner(Settings(_env_file=None, data_dir=tmp_path / "data"), detector=RecordedDetector())
    report = runner.run(video_factory(), [[0, 0], [159, 0], [159, 119], [0, 119]], 1, 1, tmp_path / "run")
    assert report["status"] == "decoder_reached_end"
    assert report["frames"] == 25
    assert len(report["events"]) == 1
    assert report["events"][0]["seconds"] > 1
    assert report["evidence_mode"] is True
    assert report["readable_labels"] is True
    assert report["stable_ids"] is True
    assert report["full_frame_context"] is False
    assert report["image_size"] == 640
    assert report["overlap_fraction"] == .7
    assert Path(report["output_dir"], "annotated.mp4").is_file()


def test_environment_overrides_infrastructure_without_changing_cv_defaults(tmp_path, monkeypatch):
    from config import Settings
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    settings = Settings(_env_file=None)
    assert settings.data_dir == tmp_path
    assert settings.image_size == 640
    assert settings.overlap_fraction == .70
    assert settings.max_hidden_seconds == 1.5
    assert settings.max_image_seconds == settings.max_body_reference_seconds == 2
