"""Translate web inputs to cells 2, 12 and 13 without changing CV logic."""
import gc
import hashlib
import importlib.metadata
import os
from pathlib import Path

import cv2
import numpy as np

from config import Settings
from .cv.media_utils import padded_crop


class PipelineRunner:
    def __init__(self, settings: Settings, detector=None):
        self.settings = settings
        self.detector = detector

    def _prepare_detector(self, crop, width, height):
        import torch
        from .cv.live_pipeline import YoloDetector, context_image_size

        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        cv2.setNumThreads(1)
        size = (context_image_size(self.settings.image_size, width, height, crop)
                if self.settings.full_frame_context else self.settings.image_size)
        device = self.settings.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if not self.settings.model_path.is_file():
            raise FileNotFoundError(f"Model weights not found: {self.settings.model_path}")
        if self.detector is None or self.detector.image_size != size:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.detector = YoloDetector(str(self.settings.model_path), device, size)
        left, top, right, bottom = crop
        dummy = np.zeros((bottom - top, right - left, 3), np.uint8)
        try:
            self.detector.predict(dummy)
        except torch.cuda.OutOfMemoryError:
            self.detector = None
            gc.collect()
            torch.cuda.empty_cache()
            self.detector = YoloDetector(str(self.settings.model_path), "cpu", size)
            self.detector.predict(dummy)

    def run(self, path, polygon, n, seconds, output_root):
        import av
        from .cv.live_pipeline import process

        with av.open(str(path)) as video:
            first = next(video.decode(video.streams.video[0]))
            width, height = first.width, first.height
        crop = ([0, 0, width, height] if self.settings.full_frame_context
                else padded_crop(polygon, width, height))
        if self.detector is None:
            self._prepare_detector(crop, width, height)
        report = process(
            path, polygon, n, seconds, self.detector, output_root,
            overlap=self.settings.overlap_fraction, crop=crop,
            max_hidden_seconds=self.settings.max_hidden_seconds,
            max_image_seconds=self.settings.max_image_seconds,
            max_extent_seconds=self.settings.max_body_reference_seconds,
            write_video=True, max_frame_gap=self.settings.max_frame_gap_seconds,
            evidence_mode=True, readable_labels=True,
            full_frame_context=self.settings.full_frame_context, stable_ids=True,
        )
        return report
