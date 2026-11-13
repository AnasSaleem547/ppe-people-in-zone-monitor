import hashlib
import importlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_modules_preserve_notebook_bodies():
    snapshot = json.loads((ROOT / "provenance/notebook_cells.json").read_text())
    for filename, source in snapshot["modules"].items():
        path = ROOT / "services/cv" / filename
        assert path.is_file(), f"Missing notebook module: {filename}"
        packaged = path.read_text()
        for name in snapshot["module_names"]:
            packaged = packaged.replace(f"from .{name} import ", f"from {name} import ")
        assert packaged == source, f"CV implementation changed: {filename}"


def test_strict_timer_direct_confirmation_and_estimated_reset():
    from services.cv.live_pipeline import Episode
    e = Episode(2, 1)
    assert e.step(Fraction(0), 2, 2) == (0, False)
    assert e.step(Fraction(1), 2, 2) == (1, False)
    assert e.step(Fraction(11, 10), 2, 1)[1] is False
    assert e.step(Fraction(12, 10), 2, 2)[1] is True
    assert e.step(Fraction(13, 10), 2, 0)[1] is False
    assert e.gate.fired is True
    assert e.step(Fraction(14, 10), 1, 1) == (0, False)
    assert e.gate.fired is False
    e.step(Fraction(2), 2, 2)
    assert e.step(Fraction(31, 10), 2, 2)[1] is True


def test_concave_polygon_allowed_crossed_or_outside_rejected():
    from services.cv.media_utils import validate_polygon
    assert validate_polygon([[0, 0], [90, 0], [30, 30], [0, 90]], 100, 100).area > 0
    for points in ([[0, 0], [90, 90], [90, 0], [0, 90]],
                   [[0, 0], [100, 0], [90, 90], [0, 90]]):
        with pytest.raises(ValueError):
            validate_polygon(points, 100, 100)


def test_rendering_matches_original_notebook_module():
    from services.cv.annotation import render
    snapshot = json.loads((ROOT / "provenance/notebook_cells.json").read_text())
    original = {}
    exec(snapshot["modules"]["annotation.py"], original)
    image = np.full((120, 160, 3), 50, np.uint8)
    polygon = [[0, 0], [159, 0], [159, 119], [0, 119]]
    tracks = [dict(id=1, score=.8, state="visible_inside", xyxy=[20, 20, 80, 110])]
    args = (image, polygon, tracks, 1, 1, 1, 2.1, 2, 2.1, True)
    actual = render(*args)
    assert actual.shape == (192, 160, 3)
    np.testing.assert_array_equal(actual, original["render"](*args))
