"""Preview and preflight only; inference always receives the original file."""
import base64
import math
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np
from backend.core import config as cfg


def image_data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def inspect_video(path):
    try:
        with av.open(str(path)) as video:
            if not video.streams.video:
                raise ValueError("The file has no video stream.")
            stream = video.streams.video[0]
            stream.codec_context.thread_count = cfg.VIDEO_DECODE_THREADS
            first = next(video.decode(stream), None)
            if first is None or first.time is None:
                raise ValueError("No readable starting video frame with a timestamp.")
            image = first.to_ndarray(format="bgr24")
            height, width = image.shape[:2]
            scale = min(1., cfg.PREVIEW_MAX_WIDTH / width)
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


def validate_video(path, max_frame_gap, max_duration_seconds=None):
    count, previous, origin, size = 0, None, None, None
    spacing, final_duration = None, None
    try:
        with av.open(str(path)) as video:
            if not video.streams.video:
                raise ValueError("No video stream.")
            stream = video.streams.video[0]
            stream.codec_context.thread_count = cfg.VIDEO_DECODE_THREADS
            nominal_spacing = Fraction(1, 1) / (stream.average_rate or cfg.MEDIA_FALLBACK_FPS)
            for frame in video.decode(stream):
                if frame.pts is None or frame.is_corrupt:
                    raise ValueError("Corrupt video frame or missing timestamp.")
                stamp = Fraction(frame.pts) * frame.time_base
                if previous is not None and (stamp <= previous or stamp - previous > max_frame_gap):
                    raise ValueError("Unusable timestamp order or excessive video gap.")
                if size is not None and size != (frame.width, frame.height):
                    raise ValueError("Video dimensions change during the recording.")
                if previous is not None:
                    spacing = stamp - previous
                final_duration = frame.duration * frame.time_base if frame.duration else None
                size = (frame.width, frame.height)
                origin = stamp if origin is None else origin
                if max_duration_seconds is not None and stamp - origin > max_duration_seconds:
                    raise ValueError("Video duration exceeds the configured limit.")
                previous = stamp
                count += 1
        if not count:
            raise ValueError("No readable video frames.")
        tail = final_duration or spacing or nominal_spacing
        if max_duration_seconds is not None and previous - origin + tail > Fraction(str(max_duration_seconds)):
            raise ValueError("Video duration exceeds the configured limit.")
        return dict(frames=count, last_video_seconds=float(previous - origin),
                    duration_seconds=float(previous - origin + tail))
    except av.FFmpegError as exc:
        raise ValueError("Video decoding failed during background validation.") from exc


def region_preview(jpeg, polygon, original_width, original_height):
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not read the saved preview.")
    points = np.asarray(polygon, dtype=float).copy()
    points[:, 0] *= image.shape[1] / original_width
    points[:, 1] *= image.shape[0] / original_height
    cv2.polylines(image, [np.rint(points).astype(np.int32)], True, cfg.PREVIEW_REGION_COLOR, cfg.PREVIEW_REGION_THICKNESS, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("Could not encode the marked region.")
    return encoded.tobytes()


def video_endpoint(path):
    """Read the VIDEO endpoint, excluding a potentially longer audio track."""
    with av.open(str(path)) as video:
        stream = video.streams.video[0]
        if stream.duration is not None:
            return float(stream.duration * stream.time_base)
        previous, last, duration = None, None, None
        for frame in video.decode(stream):
            previous, last = last, float(frame.time)
            if frame.duration:
                duration = float(frame.duration * frame.time_base)
        if last is None:
            raise ValueError("No output video frames.")
        spacing = duration or (last - previous if previous is not None else float(1 / (stream.average_rate or cfg.MEDIA_FALLBACK_FPS)))
        return last + spacing
