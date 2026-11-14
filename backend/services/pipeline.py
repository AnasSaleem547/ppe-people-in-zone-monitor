"""Translate accepted inputs and the saved zone policy to the CV runner."""
import gc
import os

import cv2
import numpy as np

from backend.core.config import Settings
from backend.core import config as cfg
from .cv.media_utils import padded_crop
from .model_assets import ensure_model


class PipelineRunner:
    def __init__(self, settings: Settings, detector=None):
        self.settings = settings
        self.detector = detector

    def _prepare_detector(self, crop, width, height):
        import torch
        from .cv.live_pipeline import YoloDetector, context_image_size

        torch.set_num_threads(max(1, min(cfg.CPU_MAX_THREADS, os.cpu_count() or 1)))
        cv2.setNumThreads(cfg.OPENCV_THREADS)
        size = (context_image_size(self.settings.image_size, width, height, crop)
                if self.settings.full_frame_context else self.settings.image_size)
        device = self.settings.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        ensure_model(self.settings)
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

    def run(self, path, polygon, n, seconds, output_root, zone_policy=None):
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
            overlap=(zone_policy or self.settings.zone_policy).get("overlap_fraction", self.settings.overlap_fraction), crop=crop,
            zone_policy=zone_policy or self.settings.zone_policy,
            max_hidden_seconds=self.settings.max_hidden_seconds,
            max_image_seconds=self.settings.max_image_seconds,
            max_extent_seconds=self.settings.max_body_reference_seconds,
            write_video=cfg.PIPELINE_WRITE_VIDEO, max_frame_gap=self.settings.max_frame_gap_seconds,
            evidence_mode=cfg.PIPELINE_EVIDENCE_MODE, readable_labels=cfg.PIPELINE_READABLE_LABELS,
            full_frame_context=self.settings.full_frame_context, stable_ids=cfg.PIPELINE_STABLE_IDS,
        )
        return report
