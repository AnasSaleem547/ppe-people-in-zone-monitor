# Cell 5 — timestamp-preserving writer and strict timer; stream outputs to disk.
from backend.core import config as cfg
import math
from fractions import Fraction
from pathlib import Path
import av,cv2,numpy as np
from shapely.geometry import Polygon
FOOTER_HEIGHT=cfg.MEDIA_FOOTER_HEIGHT

class Gate:
    # Video timestamps determine duration; computer processing time does not.
    # Alternative: frame_index/FPS. Not used because uploaded videos may vary in frame rate.
    def __init__(self, n, seconds):
        if (
            isinstance(n, bool)
            or not isinstance(n, int)
            or n < 1
            or not math.isfinite(seconds)
            or seconds <= 0
        ):
            raise ValueError("N must be a positive integer; T must be finite and positive.")
        self.n, self.seconds = n, Fraction(str(seconds))
        self.start = self.previous = None
        self.fired = False

    def step(self, t, count):
        if not math.isfinite(t) or (
            self.previous is not None and t <= self.previous
        ):
            raise ValueError("Missing, repeated, or backwards video timestamp.")
        self.previous = t

        # Strict reset: no grace period that could conceal a genuine departure.
        if count < self.n:
            self.start = None
            self.fired = False
            return 0.0, False

        if self.start is None:
            self.start = t

        elapsed = t - self.start
        alarm = elapsed > self.seconds and not self.fired
        self.fired |= alarm   # One alarm per continuous qualifying episode.
        return elapsed, alarm

def validate_polygon(points, width, height):
    a = np.asarray(points, dtype=float)
    if (
        a.shape != (cfg.JOB_POLYGON_POINT_COUNT, 2)
        or not np.isfinite(a).all()
        or len(np.unique(a, axis=0)) != cfg.JOB_POLYGON_POINT_COUNT
    ):
        raise ValueError("Choose four distinct finite points.")
    if (a < 0).any() or (a[:, 0] >= width).any() or (a[:, 1] >= height).any():
        raise ValueError("Points must be inside the image.")

    p = Polygon(a)
    # Concave quadrilaterals are allowed; crossed edges are not.
    if not p.is_valid or p.area <= 0:
        raise ValueError("Polygon edges must not cross; area must be positive.")
    return p

class AnnotatedVideo:
    def __init__(self, target, width, height):
        self.container = av.open(target, mode="w", format="mp4")
        self.origin = None
        self.previous_pts = None

        # Preserve variable frame spacing to microsecond precision.
        # Alternative: constant-FPS OpenCV writer; rejected because it can change playback timing.
        self.time_base = Fraction(1, cfg.MEDIA_TIME_BASE_DENOMINATOR)

        try:
            # CPU H.264 encoding works without depending on a particular GPU encoder.
            # rate=30 supplies a nominal rate; explicit timestamps below control frame timing.
            self.stream = self.container.add_stream(cfg.MEDIA_ENCODER, rate=cfg.MEDIA_NOMINAL_FPS)

            # Widely supported yuv420p video requires even dimensions.
            # Pad at most one row/column instead of resizing the monitored scene.
            self.stream.width = width + width % 2
            self.stream.height = height + height % 2
            self.stream.pix_fmt = "yuv420p"

            self.stream.time_base = self.time_base
            self.stream.codec_context.time_base = self.time_base

            # Bound encoder CPU concurrency instead of competing for every core.
            self.stream.codec_context.thread_count = cfg.MEDIA_ENCODER_THREADS

            # veryfast trades larger files for less encoding work.
            # zerolatency avoids buffering future frames for encoder lookahead.
            # CRF controls compression quality; lower values mean larger, clearer files.
            self.stream.options = {
                "preset": cfg.MEDIA_ENCODER_PRESET,
                "crf": cfg.MEDIA_ENCODER_CRF,
                "tune": cfg.MEDIA_ENCODER_TUNE,
            }
        except Exception:
            self.container.close()
            raise

    def write(self, image, timestamp):
        timestamp = Fraction(timestamp)
        if self.origin is None:
            self.origin = timestamp

        # Start output at zero while retaining spacing between source timestamps.
        pts = round((timestamp - self.origin) / self.time_base)
        if self.previous_pts is not None and pts <= self.previous_pts:
            raise ValueError(
                "Output timestamps must increase at microsecond precision."
            )

        h, w = image.shape[:2]
        if h % 2 or w % 2:
            image = np.pad(
                image,
                ((0, h % 2), (0, w % 2), (0, 0)),
                mode="constant",
            )

        # Encode immediately; do not collect video frames in a Python list.
        output_frame = av.VideoFrame.from_ndarray(image, format="bgr24")
        output_frame.pts = pts
        output_frame.time_base = self.time_base

        for packet in self.stream.encode(output_frame):
            self.container.mux(packet)

        self.previous_pts = pts

    def close(self):
        if self.container is not None:
            try:
                # Flush remaining encoded data so the last frames are not lost.
                for packet in self.stream.encode():
                    self.container.mux(packet)
            finally:
                # Closing writes the MP4 structures needed for playback.
                self.container.close()
                self.container = None

def status_frame(image, text, color):
    # Extend the encoded frame below the camera view. Detection uses original coordinates.
    output = cv2.copyMakeBorder(image, 0, cfg.MEDIA_FOOTER_HEIGHT, 0, 0,
                                cv2.BORDER_CONSTANT, value=cfg.MEDIA_FOOTER_COLOR)
    font = cfg.MEDIA_FONT
    text_width = cv2.getTextSize(text, font, cfg.MEDIA_STATUS_MEASURE_SCALE, cfg.MEDIA_STATUS_THICKNESS)[0][0]
    scale = min(cfg.MEDIA_STATUS_MAX_SCALE, max(1, image.shape[1] - cfg.MEDIA_STATUS_HORIZONTAL_PADDING) / max(1, text_width))
    cv2.putText(output, text, (cfg.MEDIA_STATUS_X, image.shape[0] + cfg.MEDIA_STATUS_BASELINE_OFFSET), font, scale, color, cfg.MEDIA_STATUS_THICKNESS, cfg.MEDIA_LINE_TYPE)
    return output

def bundle_run(folder):
    import zipfile
    # Each processing run has its own directory. Archive its files together.
    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in sorted(folder.iterdir()):
            if path.is_file():
                method = zipfile.ZIP_STORED if path.suffix in (".mp4", ".jpg") else zipfile.ZIP_DEFLATED
                bundle.write(path, path.name, compress_type=method)
    return archive

def padded_crop(polygon,width,height,margin=cfg.MEDIA_CROP_MARGIN):
    p=np.asarray(polygon,float);padding=margin*(p.max(0)-p.min(0))
    return np.r_[np.maximum(0,np.floor(p.min(0)-padding)),
                 np.minimum([width,height],np.ceil(p.max(0)+padding)+1)].astype(int).tolist()

def package_versions(names):
    import importlib.metadata
    result={}
    for name in names:
        try:result[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:result[name]=None
    return result
