"""Preview and preflight only; inference always receives the original file."""
import base64
import math
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np


def image_data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def inspect_video(path):
    try:
        with av.open(str(path)) as video:
            if not video.streams.video:
                raise ValueError("The file has no video stream.")
            stream = video.streams.video[0]
            stream.codec_context.thread_count = 2
            first = next(video.decode(stream), None)
            if first is None or first.time is None:
                raise ValueError("No readable starting video frame with a timestamp.")
            image = first.to_ndarray(format="bgr24")
            height, width = image.shape[:2]
            scale = min(1., 960 / width)
            preview = cv2.resize(image, (round(width * scale), round(height * scale)))
            ok, encoded = cv2.imencode(".jpg", preview)
            if not ok:
                raise ValueError("Could not encode the video preview.")
            duration = None
            if stream.duration is not None and stream.start_time is not None:
                candidate = float((stream.start_time + stream.duration) * stream.time_base) - float(first.time)
                if math.isfinite(candidate) and candidate > 0:
                    duration = candidate
            return dict(width=width, height=height, preview_width=preview.shape[1],
                        preview_height=preview.shape[0], duration_seconds=duration,
                        first_timestamp=float(first.time), jpeg=encoded.tobytes())
    except av.FFmpegError as exc:
        raise ValueError("Could not read the uploaded video.") from exc


def validate_video(path, max_frame_gap):
    count, previous, origin, size = 0, None, None, None
    try:
        with av.open(str(path)) as video:
            if not video.streams.video:
                raise ValueError("No video stream.")
            stream = video.streams.video[0]
            stream.codec_context.thread_count = 2
            for frame in video.decode(stream):
                if frame.pts is None or frame.is_corrupt:
                    raise ValueError("Corrupt video frame or missing timestamp.")
                stamp = Fraction(frame.pts) * frame.time_base
                if previous is not None and (stamp <= previous or stamp - previous > max_frame_gap):
                    raise ValueError("Unusable timestamp order or excessive video gap.")
                if size is not None and size != (frame.width, frame.height):
                    raise ValueError("Video dimensions change during the recording.")
                size = (frame.width, frame.height)
                origin = stamp if origin is None else origin
                previous = stamp
                count += 1
        if not count:
            raise ValueError("No readable video frames.")
        return dict(frames=count, last_video_seconds=float(previous - origin))
    except av.FFmpegError as exc:
        raise ValueError("Video decoding failed during background validation.") from exc


def region_preview(jpeg, polygon, original_width, original_height):
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not read the saved preview.")
    points = np.asarray(polygon, dtype=float).copy()
    points[:, 0] *= image.shape[1] / original_width
    points[:, 1] *= image.shape[0] / original_height
    cv2.polylines(image, [np.rint(points).astype(np.int32)], True, (20, 230, 240), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("Could not encode the marked region.")
    return encoded.tobytes()
