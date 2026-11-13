from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def video_factory(tmp_path):
    def make(name="input.mp4", times=None, width=160, height=120):
        import av
        times = times if times is not None else [Fraction(i, 10) for i in range(25)]
        path = tmp_path / name
        with av.open(str(path), "w") as out:
            stream = out.add_stream("libx264", rate=10)
            stream.width, stream.height = width, height
            stream.pix_fmt = "yuv420p"
            stream.time_base = Fraction(1, 1000000)
            stream.codec_context.time_base = stream.time_base
            for i, t in enumerate(times):
                image = np.full((height, width, 3), 40 + i % 30, dtype=np.uint8)
                frame = av.VideoFrame.from_ndarray(image, format="bgr24")
                frame.pts = round(t * 1000000)
                frame.time_base = Fraction(1, 1000000)
                for packet in stream.encode(frame):
                    out.mux(packet)
            for packet in stream.encode():
                out.mux(packet)
        return path
    return make
