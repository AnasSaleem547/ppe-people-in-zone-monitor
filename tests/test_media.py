import base64
from fractions import Fraction

import cv2
import numpy as np
import pytest


def test_preview_uses_actual_dimensions_and_background_validation_reads_all_frames(video_factory):
    from services.media import inspect_video, validate_video
    p = video_factory(width=1000, height=126)
    preview = inspect_video(p)
    assert preview["width"] == 1000
    assert preview["height"] == 126
    assert preview["preview_width"] == 960
    assert preview["preview_height"] == 121
    image = cv2.imdecode(np.frombuffer(preview["jpeg"], np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (121, 960)
    checked = validate_video(p, 1)
    assert checked["frames"] == 25
    assert checked["duration_seconds"] == pytest.approx(2.5)


def test_preflight_rejects_timestamp_gap_after_a_readable_first_frame(video_factory):
    from services.media import inspect_video, validate_video
    path = video_factory(times=[Fraction(0), Fraction(1, 10), Fraction(3)])
    assert inspect_video(path)["width"] == 160
    with pytest.raises(ValueError, match="gap"):
        validate_video(path, 1)


def test_region_preview_marks_same_first_frame_in_original_coordinates(video_factory):
    from services.media import inspect_video, region_preview
    preview = inspect_video(video_factory(width=1000, height=126))
    points = [[100, 10], [800, 10], [800, 100], [100, 100]]
    result = region_preview(preview["jpeg"], points, 1000, 126)
    image = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (121, 960)
    # x=100 maps to x=96, y=50 maps to y≈48; the left edge is colored.
    assert int(image[48, 96].max()) - int(image[48, 96].min()) > 80
    assert abs(int(image[48, 500].max()) - int(image[48, 500].min())) < 10


def test_bad_media_is_rejected(tmp_path):
    from services.media import inspect_video
    p = tmp_path / "fake.mp4"
    p.write_bytes(b"not a video")
    with pytest.raises(ValueError, match="video"):
        inspect_video(p)
