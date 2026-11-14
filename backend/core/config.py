"""Runtime configuration, CV thresholds, and an explicit zone membership policy.

Edit CV constants here and restart processes to apply them. Each comment names
the consumer. These are heuristics, not universal accuracy guarantees.
Lowercase Settings fields also support environment overrides through Pydantic.
"""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
# Streamlit and FastAPI run on the same VM; this is not a server bind address.
BACKEND_URL = "http://127.0.0.1:8010"


# Existing CV tuning defaults are preserved except for the explicitly selected
# anchor membership policy and its bounded boundary uncertainty below.
# Array indices/dimensions, algebraic 0/1/2, fixed unit conversions (e.g. 100 percent,
# 1024 bytes/KiB), HTTP status codes and codec pixel-format constraints are structural,
# not tuning. Model weights and Kalman-filter mathematics remain in pinned dependencies.
# CV and browser configuration changes require restarting API, worker and frontend.
# For constructors/schema defaults, Python binds values when their modules are imported.
# Standard Ultralytics weights; live_pipeline.YoloDetector and Settings.model_name.
MODEL_NAME = 'yolo26m.pt'
# Direct detector construction default; live_pipeline.YoloDetector (web Settings chooses auto).
DETECTOR_DEFAULT_DEVICE = 'cpu'
# YOLO input side length; live_pipeline.YoloDetector and Settings.image_size.
DETECTOR_IMAGE_SIZE = 640
# YOLO input alignment multiple; live_pipeline.context_image_size.
DETECTOR_STRIDE = 32
# Reject full-frame context above this input side; live_pipeline.context_image_size.
DETECTOR_MAX_CONTEXT_SIZE = 1024
# COCO person class only; live_pipeline.YoloDetector.predict.
DETECTOR_CLASSES = [0]
# Minimum raw YOLO confidence; live_pipeline.YoloDetector.predict, before tracking filters.
DETECTOR_CONFIDENCE = .05
# YOLO suppression IoU argument; live_pipeline.YoloDetector.predict (backend/model may use NMS-free inference).
DETECTOR_NMS_IOU = .7
# Detection cap; reaching it raises instead of silently undercounting; live_pipeline.YoloDetector.predict.
DETECTOR_MAX_DETECTIONS = 300
# Use half precision on CUDA only; live_pipeline.YoloDetector.predict.
DETECTOR_CUDA_HALF = True
# Large area growth gate; live_pipeline.compatible_extent.
TRACK_EXPANSION_AREA_RATIO = 2.
# Height growth gate paired with area growth; live_pipeline.compatible_extent.
TRACK_EXPANSION_HEIGHT_RATIO = 1.25
# Minimum crop-edge tolerance in pixels; live_pipeline.edge_expansion.
TRACK_EDGE_TOLERANCE_PIXELS = 4.
# Crop-size-relative edge tolerance; live_pipeline.edge_expansion.
TRACK_EDGE_TOLERANCE_FRACTION = .02
# Minimum smaller-box containment for shared-edge expansion; live_pipeline.edge_expansion.
TRACK_EDGE_MIN_CONTAINMENT = .7
# Below this IoU a proposed person match is weak; live_pipeline.ExtentTracker.get_dists.
TRACK_NEIGHBOUR_OWN_MAX_IOU = .3
# At least this IoU suggests a visible neighbour owns the detection; live_pipeline.ExtentTracker.get_dists.
TRACK_NEIGHBOUR_OTHER_MIN_IOU = .5
# Below this IoU treat the two existing boxes as separate people; live_pipeline.ExtentTracker.get_dists.
TRACK_NEIGHBOUR_PAIR_MAX_IOU = .3
# IoU needed to apply low-confidence extent rejection; live_pipeline.ExtentTracker.init_track.
TRACK_LOW_SCORE_MIN_IOU = .2
# ByteTrack first-association confidence; live_pipeline.make_tracker.
TRACK_HIGH_CONFIDENCE = .25
# ByteTrack second-association lower confidence; live_pipeline.make_tracker.
TRACK_LOW_CONFIDENCE = .1
# Confidence required to start a new identity; live_pipeline.make_tracker.
TRACK_NEW_CONFIDENCE = .6
# ByteTrack lost-frame buffer, scaled internally by source FPS; live_pipeline.make_tracker.
TRACK_BUFFER_FRAMES = 60
# Maximum first-association cost (1-IoU); live_pipeline.make_tracker.
TRACK_MATCH_MAX_COST = .8
# Whether ByteTrack combines confidence with matching cost; live_pipeline.make_tracker.
TRACK_FUSE_SCORE = False
# Raw-box confidence floor before ByteTrack; live_pipeline.filter_boxes.
DETECTION_MIN_CONFIDENCE = .1
# Raw-box duplicate suppression IoU; live_pipeline.filter_boxes.
DETECTION_DUPLICATE_IOU = .85
# Fraction of box area inside polygon; Settings.overlap_fraction and live_pipeline.process.
ZONE_OVERLAP_FRACTION = .70
# Maximum short missing-person retention with supporting evidence; Settings and live_pipeline.process.
HIDDEN_MAX_SECONDS = 1.5
# Maximum age of image evidence; Settings and live_pipeline.process.
IMAGE_MAX_SECONDS = 2.
# Maximum age of reliable body extent; Settings and live_pipeline.process.
BODY_MAX_REFERENCE_SECONDS = 2.
# Reject larger video-timestamp gaps; Settings and live_pipeline.process.
VIDEO_MAX_FRAME_GAP_SECONDS = 1.
# Decoder thread count; live_pipeline.process and services.media.
VIDEO_DECODE_THREADS = 2
# Source FPS fallback for tracker; live_pipeline.process.
VIDEO_FALLBACK_FPS = 25
# Non-readable-label footer height; live_pipeline.process.
LEGACY_FOOTER_HEIGHT = 32
# Confidence needed to replace image template; live_pipeline.process.
VISUAL_TEMPLATE_MIN_CONFIDENCE = .6
# Worker console frame-log interval; live_pipeline.process.
PROGRESS_LOG_EVERY_FRAMES = 250
# BGR polygon color in basic renderer; live_pipeline.process.
LEGACY_POLYGON_COLOR = (0,220,220)
# Basic polygon stroke pixels; live_pipeline.process.
LEGACY_POLYGON_THICKNESS = 2
# Basic directly detected box BGR; live_pipeline.process.
LEGACY_VISIBLE_COLOR = (0,210,0)
# Basic retained box BGR; live_pipeline.process.
LEGACY_HIDDEN_COLOR = (0,160,255)
# Basic outside box BGR; live_pipeline.process.
LEGACY_OUTSIDE_COLOR = (200,130,30)
# Basic box stroke pixels; live_pipeline.process.
LEGACY_BOX_THICKNESS = 1
# Minimum label baseline pixels; live_pipeline.process.
LEGACY_LABEL_MIN_Y = 12
# Label distance above box in pixels; live_pipeline.process.
LEGACY_LABEL_OFFSET = 3
# Basic label font scale; live_pipeline.process.
LEGACY_LABEL_SCALE = .38
# Basic label stroke pixels; live_pipeline.process.
LEGACY_LABEL_THICKNESS = 1
# Basic status text BGR; live_pipeline.process.
LEGACY_STATUS_COLOR = (255,255,255)
# Torch thread cap; services.pipeline._prepare_detector.
CPU_MAX_THREADS = 4
# OpenCV worker threads; services.pipeline._prepare_detector.
OPENCV_THREADS = 1

# Audio packaging and annotation preview defaults.
# Tone peak amplitude (0–1); services.alarms.add_alarm_audio.
ALARM_AMPLITUDE = .25
# Alarm pitch in Hz; services.alarms.add_alarm_audio.
ALARM_FREQUENCY_HZ = 880
# Audio samples per second; services.alarms.add_alarm_audio.
ALARM_SAMPLE_RATE = 48000
# Tolerance before restoring final video frame duration; services.alarms.add_alarm_audio.
ALARM_ENDPOINT_EPSILON_SECONDS = .000001
# Delivery audio codec; services.alarms.add_alarm_audio.
ALARM_AUDIO_CODEC = 'aac'
# Encoded audio bitrate; services.alarms.add_alarm_audio.
ALARM_AUDIO_BITRATE = '128k'
# Minimum FFmpeg timeout; services.alarms.add_alarm_audio.
ALARM_MIN_TIMEOUT_SECONDS = 120
# FFmpeg timeout multiplier of video duration; services.alarms.add_alarm_audio.
ALARM_TIMEOUT_DURATION_MULTIPLIER = 2
# First-frame preview maximum width in pixels; services.media.inspect_video.
PREVIEW_MAX_WIDTH = 960
# Duration fallback when rate metadata is absent; services.media.validate_video/video_endpoint.
MEDIA_FALLBACK_FPS = 30
# BGR reference polygon color; services.media.region_preview.
PREVIEW_REGION_COLOR = (20,230,240)
# Reference polygon line thickness in pixels; services.media.region_preview.
PREVIEW_REGION_THICKNESS = 2

# Area denominator floor in rectangle_iou, same_upper_extent, replaces_old_extent, Occupancy.fraction/body_reference/step; backend/services/cv/occupancy.py.
OCC_MIN_AREA = 1.
# Minimum smaller-box containment in same_upper_extent; backend/services/cv/occupancy.py.
OCC_UPPER_MIN_CONTAINMENT = .75
# Maximum upper center offset relative to smaller width in same_upper_extent; backend/services/cv/occupancy.py.
OCC_UPPER_MAX_CENTER_OFFSET = .25
# Maximum top-edge offset relative to smaller height in same_upper_extent; backend/services/cv/occupancy.py.
OCC_UPPER_MAX_TOP_OFFSET = .08
# Minimum height ratio in same_upper_extent; backend/services/cv/occupancy.py.
OCC_UPPER_MIN_HEIGHT_RATIO = 1.2
# Minimum intersection-over-union to identify a replacement in replaces_old_extent; backend/services/cv/occupancy.py.
OCC_REPLACEMENT_MIN_IOU = .7
# Minimum current-box containment in replaces_old_extent; backend/services/cv/occupancy.py.
OCC_REPLACEMENT_MIN_CONTAINMENT = .65
# Maximum top-edge offset relative to prior height in replaces_old_extent; backend/services/cv/occupancy.py.
OCC_REPLACEMENT_MAX_TOP_OFFSET = .2
# Maximum replacement height relative to prior height in replaces_old_extent; backend/services/cv/occupancy.py.
OCC_REPLACEMENT_MAX_HEIGHT_RATIO = 1.2
# Maximum replacement area relative to prior area in replaces_old_extent; backend/services/cv/occupancy.py.
OCC_REPLACEMENT_MAX_AREA_RATIO = 1.2
# Default polygon-overlap membership threshold in Occupancy.__init__; backend/services/cv/occupancy.py.
OCC_DEFAULT_OVERLAP = ZONE_OVERLAP_FRACTION
# Default supported missing-person retention seconds in Occupancy.__init__; backend/services/cv/occupancy.py.
OCC_DEFAULT_MAX_HIDDEN_SECONDS = HIDDEN_MAX_SECONDS
# Default cover/partial-body inference switch in Occupancy.__init__; backend/services/cv/occupancy.py.
OCC_DEFAULT_EVIDENCE_MODE = False
# Default maximum body-reference age seconds in Occupancy.__init__; backend/services/cv/occupancy.py.
OCC_DEFAULT_MAX_EXTENT_SECONDS = BODY_MAX_REFERENCE_SECONDS
# Maximum contracted-box width relative to reference in Occupancy.body_reference; backend/services/cv/occupancy.py.
OCC_REFERENCE_MAX_WIDTH_RATIO = 1.2
# Maximum center displacement relative to width in Occupancy.body_reference; backend/services/cv/occupancy.py.
OCC_REFERENCE_MAX_CENTER_OFFSET = .5
# Maximum top-edge displacement relative to height in Occupancy.body_reference; backend/services/cv/occupancy.py.
OCC_REFERENCE_MAX_TOP_OFFSET = .2
# Minimum contracted-box containment in Occupancy.body_reference; backend/services/cv/occupancy.py.
OCC_REFERENCE_MIN_CONTAINMENT = .75
# Minimum retained-height fraction that refreshes reference time in Occupancy.body_reference; backend/services/cv/occupancy.py.
OCC_REFERENCE_RELIABLE_HEIGHT_RATIO = .95
# Minimum overlap for retained-person reconnection in Occupancy.step; backend/services/cv/occupancy.py.
OCC_RECONNECT_MIN_IOU = .7
# Minimum raw-box score for retained-person reconnection in Occupancy.step; backend/services/cv/occupancy.py.
OCC_RECONNECT_MIN_CONFIDENCE = .6
# Minimum prior-body fraction covered by blocker in Occupancy.step; backend/services/cv/occupancy.py.
OCC_BLOCKER_MIN_OVERLAP = .35
# Minimum blocker area relative to prior-body area in Occupancy.step; backend/services/cv/occupancy.py.
OCC_BLOCKER_MIN_AREA_RATIO = 1.2
# Minimum polygon-boundary distance relative to body short side in Occupancy.step; backend/services/cv/occupancy.py.
OCC_DEEP_INTERIOR_MARGIN = .1
# Fallback timestamp for absent blocker evidence in Occupancy.step; backend/services/cv/occupancy.py.
OCC_NEVER_SEEN_TIME = -1e9
# Maximum age of recent blocker evidence in Occupancy.step; backend/services/cv/occupancy.py.
OCC_BLOCKER_MEMORY_SECONDS = .5
# Minimum lost-identity storage seconds in Occupancy.step; backend/services/cv/occupancy.py.
OCC_MIN_IDENTITY_RETENTION_SECONDS = 2.
# Default maximum stored-template age seconds in VisualSupport.__init__; backend/services/cv/visual_support.py.
VIS_DEFAULT_MAX_AGE = IMAGE_MAX_SECONDS
# Default minimum matching eligible-patch fraction in VisualSupport.__init__; backend/services/cv/visual_support.py.
VIS_DEFAULT_MINIMUM_FRACTION = .25
# Minimum usable crop width pixels in VisualSupport._crop; backend/services/cv/visual_support.py.
VIS_MIN_CROP_WIDTH = 12
# Minimum usable crop height pixels in VisualSupport._crop; backend/services/cv/visual_support.py.
VIS_MIN_CROP_HEIGHT = 16
# Normalized template width pixels in VisualSupport._crop/verify; backend/services/cv/visual_support.py.
VIS_TEMPLATE_WIDTH = 64
# Normalized template height pixels in VisualSupport._crop/verify; backend/services/cv/visual_support.py.
VIS_TEMPLATE_HEIGHT = 96
# Vertical patch origins on normalized template in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_PATCH_ROWS = (16,36,56,72)
# Horizontal patch origins on normalized template in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_PATCH_COLUMNS = (12,28,44)
# Square comparison patch side pixels in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_PATCH_SIZE = 12
# Patch-area denominator floor in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MIN_AREA = 1.
# Maximum patch overlap with a currently observed person in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MAX_OCCUPIED_FRACTION = .25
# Minimum intensity standard deviation for informative patches in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MIN_PATCH_STDDEV = 6
# Eight-bit grayscale intensity normalization in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_INTENSITY_MAX = 255
# Minimum normalized patch correlation in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MIN_CORRELATION = .85
# Maximum normalized mean absolute patch difference in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MAX_DIFFERENCE = .12
# Minimum agreeing patches for visual support in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MIN_MATCHING_PATCHES = 3
# Minimum informative patches for visual support in VisualSupport.verify; backend/services/cv/visual_support.py.
VIS_MIN_ELIGIBLE_PATCHES = 3
# Image and box downscale factor in CoverEvidence.update/covers; backend/services/cv/cover_evidence.py.
COVER_IMAGE_SCALE = .5
# Minimum grayscale pixel change for motion mask in CoverEvidence.update; backend/services/cv/cover_evidence.py.
COVER_MOTION_MIN_DELTA = 25
# Eight-bit mask maximum and intensity normalization in CoverEvidence.update/covers; backend/services/cv/cover_evidence.py.
COVER_INTENSITY_MAX = 255
# Closing-kernel width and height pixels at scaled resolution in CoverEvidence.update; backend/services/cv/cover_evidence.py.
COVER_MORPH_KERNEL_SIZE = (7,7)
# Minimum moving component area pixels at scaled resolution in CoverEvidence.update; backend/services/cv/cover_evidence.py.
COVER_MIN_COMPONENT_AREA = 30
# Person-area denominator floor at scaled resolution in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_MIN_AREA = 1.
# Maximum surrounding-ring difference from pre-cover baseline to clear evidence in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_RING_BASELINE_MAX_DIFFERENCE = .08
# Maximum footprint difference from pre-cover baseline to clear evidence in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_BASELINE_MAX_DIFFERENCE = .10
# Minimum person-footprint fraction covered by moving component in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_MIN_PERSON_OVERLAP = .35
# Minimum component area relative to person footprint in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_MIN_COMPONENT_AREA_RATIO = 1.2
# Maximum footprint difference from saved cover appearance to retain evidence in CoverEvidence.covers; backend/services/cv/cover_evidence.py.
COVER_SAVED_MAX_DIFFERENCE = .10



# Identity linking, readable annotation, and media writer tuning.
# Maximum remembered identity age in video seconds; identity_link.IdentityLinker.
IDENTITY_MAX_AGE_SECONDS = 30.
# Maximum colour distance for a normal return; identity_link.IdentityLinker.
IDENTITY_MAX_APPEARANCE_DISTANCE = .22
# Required colour-distance gap between best two candidates; identity_link.IdentityLinker.
IDENTITY_MINIMUM_MARGIN = .08
# Minimum crop-edge tolerance in pixels; identity_link.IdentityLinker.
IDENTITY_EDGE_TOLERANCE_PIXELS = 2.
# Crop-size-relative crop-edge tolerance; identity_link.IdentityLinker.
IDENTITY_EDGE_TOLERANCE_FRACTION = .02
# Surrounding original-image context as fraction of detected extent; identity_link.IdentityLinker.
IDENTITY_CROP_CONTEXT_EXPANSION = .75
# Horizontal and vertical inset fractions for colour crop; identity_link.IdentityLinker.
IDENTITY_FEATURE_INSET = (.15,.1)
# Minimum colour-crop side length in pixels; identity_link.IdentityLinker.
IDENTITY_MIN_CROP_SIDE = 8
# Resized colour crop width and height in pixels; identity_link.IdentityLinker.
IDENTITY_FEATURE_SIZE = (32,64)
# Hue and saturation histogram bin counts; identity_link.IdentityLinker.
IDENTITY_HS_HISTOGRAM_BINS = (8,8)
# OpenCV HSV hue and saturation histogram ranges; identity_link.IdentityLinker.
IDENTITY_HS_HISTOGRAM_RANGES = (0,180,0,256)
# Brightness histogram bin count; identity_link.IdentityLinker.
IDENTITY_VALUE_HISTOGRAM_BINS = (16,)
# OpenCV HSV brightness histogram range; identity_link.IdentityLinker.
IDENTITY_VALUE_HISTOGRAM_RANGE = (0,256)
# Hue/saturation histogram mixture weight; identity_link.IdentityLinker.
IDENTITY_HS_FEATURE_WEIGHT = .6
# Brightness histogram mixture weight; identity_link.IdentityLinker.
IDENTITY_VALUE_FEATURE_WEIGHT = .4
# Minimum detection confidence for remembering colour; identity_link.IdentityLinker.
IDENTITY_REMEMBER_MIN_CONFIDENCE = .6
# Minimum interval between stored colour samples; identity_link.IdentityLinker.
IDENTITY_FEATURE_INTERVAL_SECONDS = 1.
# Maximum stored whole-body colour features; identity_link.IdentityLinker.
IDENTITY_FEATURE_HISTORY_SIZE = 3
# Vertical body-part sampling intervals; identity_link.IdentityLinker.
IDENTITY_BODY_PART_FRACTIONS = ((0.,1/3),(1/3,2/3),(2/3,1.))
# Maximum stored body-part colour features; identity_link.IdentityLinker.
IDENTITY_PART_HISTORY_SIZE = 9
# Minimum intersection-over-union for duplicate extents; identity_link.IdentityLinker.
IDENTITY_DUPLICATE_MIN_IOU = .7
# Maximum top-edge difference relative to smaller height; identity_link.IdentityLinker.
IDENTITY_DUPLICATE_TOP_TOLERANCE = .08
# Maximum horizontal center difference relative to smaller width; identity_link.IdentityLinker.
IDENTITY_DUPLICATE_CENTER_TOLERANCE = .2
# Minimum smaller-box containment for partial crop return; identity_link.IdentityLinker.
IDENTITY_PARTIAL_MIN_CONTAINMENT = .2
# Partial-return center-distance cap as multiple of larger height; identity_link.IdentityLinker.
IDENTITY_PARTIAL_MAX_DISTANCE_HEIGHTS = 1.
# Maximum colour distance when merging current duplicate detections; identity_link.IdentityLinker.
IDENTITY_DUPLICATE_MAX_COLOR_DISTANCE = .15
# Large area-growth rejection threshold; identity_link.IdentityLinker.
IDENTITY_EXPANSION_AREA_RATIO = 2
# Height-growth threshold paired with large area growth; identity_link.IdentityLinker.
IDENTITY_EXPANSION_HEIGHT_RATIO = 1.25
# Return center-distance cap relative to sum of box heights; identity_link.IdentityLinker.
IDENTITY_MAX_DISTANCE_HEIGHT_SUM = .75
# Relative height below which body-part features are considered; identity_link.IdentityLinker.
IDENTITY_PARTIAL_HEIGHT_RATIO = .8
# Required vertical overlap relative to smaller body-part height; identity_link.IdentityLinker.
IDENTITY_PART_MIN_VERTICAL_OVERLAP = .5
# Relaxed appearance-distance limit for shared-edge partial returns; identity_link.IdentityLinker.
IDENTITY_PARTIAL_MAX_COLOR_DISTANCE = .4
# Status footer height in pixels; annotation.render/dashed_box.
ANN_FOOTER_HEIGHT = 72
# BGR box colors by tracking state; annotation.render/dashed_box.
ANN_COLORS = {'visible_inside':(80,220,90),'image_supported':(0,255,255),'possibly_hidden':(0,255,255),'observed_outside':(230,180,100)}
# Dashed-box repeating interval in pixels; annotation.render/dashed_box.
ANN_DASH_PERIOD = 16
# Visible portion of each dash in pixels; annotation.render/dashed_box.
ANN_DASH_LENGTH = 9
# Track box stroke thickness in pixels; annotation.render/dashed_box.
ANN_BOX_THICKNESS = 2
# OpenCV anti-aliased line mode (LINE_AA); annotation.render/dashed_box.
ANN_LINE_TYPE = 16
# BGR footer background; annotation.render/dashed_box.
ANN_FOOTER_COLOR = (22,22,22)
# OpenCV Hershey Simplex font identifier; annotation.render/dashed_box.
ANN_FONT = 0
# BGR monitored-zone outline; annotation.render/dashed_box.
ANN_POLYGON_COLOR = (20,230,240)
# Zone outline stroke thickness in pixels; annotation.render/dashed_box.
ANN_POLYGON_THICKNESS = 2
# Legacy render overlap argument default; currently unused; annotation.render/dashed_box.
ANN_OVERLAP_FRACTION = .7
# Person-label font scale for narrow images; annotation.render/dashed_box.
ANN_LABEL_SCALE_SMALL = .75
# Image-width threshold for larger person labels; annotation.render/dashed_box.
ANN_LABEL_WIDE_THRESHOLD = 1100
# Person-label font scale for wide images; annotation.render/dashed_box.
ANN_LABEL_SCALE_LARGE = .8
# Person-label foreground stroke thickness; annotation.render/dashed_box.
ANN_LABEL_THICKNESS = 2
# Minimum label left edge in pixels; annotation.render/dashed_box.
ANN_LABEL_MIN_X = 2
# Person-label right margin in pixels; annotation.render/dashed_box.
ANN_LABEL_RIGHT_MARGIN = 5
# Person-label bottom baseline margin in pixels; annotation.render/dashed_box.
ANN_LABEL_BOTTOM_MARGIN = 8
# Person-label top margin in pixels; annotation.render/dashed_box.
ANN_LABEL_TOP_MARGIN = 8
# Person-label baseline offset above box; annotation.render/dashed_box.
ANN_LABEL_BOX_OFFSET = 5
# BGR person-label outline; annotation.render/dashed_box.
ANN_LABEL_OUTLINE_COLOR = (0,0,0)
# Person-label outline thickness; annotation.render/dashed_box.
ANN_LABEL_OUTLINE_THICKNESS = 5
# BGR person-label foreground; annotation.render/dashed_box.
ANN_LABEL_COLOR = (255,255,255)
# Maximum status-text font scale; annotation.render/dashed_box.
ANN_STATUS_SCALE = .60
# Total horizontal status-text fitting margin; annotation.render/dashed_box.
ANN_STATUS_HORIZONTAL_PADDING = 24
# Status text stroke thickness; annotation.render/dashed_box.
ANN_STATUS_THICKNESS = 1
# Footer text left inset in pixels; annotation.render/dashed_box.
ANN_STATUS_X = 12
# First footer text baseline below image; annotation.render/dashed_box.
ANN_STATUS_BASELINE_OFFSET = 25
# Vertical distance between footer text lines; annotation.render/dashed_box.
ANN_STATUS_LINE_SPACING = 32
# BGR status text color; annotation.render/dashed_box.
ANN_STATUS_COLOR = (245,245,245)
# Basic status footer height in pixels; media_utils.
MEDIA_FOOTER_HEIGHT = 32
# Output timestamp ticks per second; media_utils.
MEDIA_TIME_BASE_DENOMINATOR = 1_000_000
# Output video codec; media_utils.
MEDIA_ENCODER = "libx264"
# Nominal encoder frame rate; explicit timestamps preserve actual spacing; media_utils.
MEDIA_NOMINAL_FPS = 30
# Encoder CPU thread cap; media_utils.
MEDIA_ENCODER_THREADS = 2
# H.264 encoding speed and compression tradeoff; media_utils.
MEDIA_ENCODER_PRESET = "veryfast"
# H.264 constant-rate-factor quality; smaller values retain more detail; media_utils.
MEDIA_ENCODER_CRF = "23"
# Encoder latency tuning; media_utils.
MEDIA_ENCODER_TUNE = "zerolatency"
# BGR basic status footer background; media_utils.
MEDIA_FOOTER_COLOR = (25,25,25)
# OpenCV Hershey Simplex status font; media_utils.
MEDIA_FONT = 0
# Reference font scale for basic footer width measurement; media_utils.
MEDIA_STATUS_MEASURE_SCALE = 1
# Basic footer text stroke thickness; media_utils.
MEDIA_STATUS_THICKNESS = 1
# Maximum basic footer font scale; media_utils.
MEDIA_STATUS_MAX_SCALE = 0.63
# Total basic footer horizontal fitting margin; media_utils.
MEDIA_STATUS_HORIZONTAL_PADDING = 16
# Basic footer text left inset in pixels; media_utils.
MEDIA_STATUS_X = 8
# Basic footer text baseline below camera image; media_utils.
MEDIA_STATUS_BASELINE_OFFSET = 22
# OpenCV anti-aliased basic footer text mode (LINE_AA); media_utils.
MEDIA_LINE_TYPE = 16
# Detector crop padding as fraction of polygon bounding-box size; media_utils.
MEDIA_CROP_MARGIN = .15

# Minimum displayed ID field width; annotation.render person label and reserved width.
ANN_LABEL_ID_WIDTH = 3
# Detection confidence decimal places; annotation.render person label and reserved width.
ANN_CONFIDENCE_DECIMALS = 2
# Elapsed and video-time decimal places; annotation.render status line.
ANN_TIME_DECIMALS = 2

# Zone membership and bounded boundary uncertainty.
# cv/occupancy.Occupancy, cv/live_pipeline.process and Settings.zone_policy.
# Membership policy for Occupancy: 'anchor' uses the named point; 'box_overlap'
# retains the legacy ZONE_OVERLAP_FRACTION area test.
OCC_DEFAULT_MEMBERSHIP_MODE = 'anchor'
# Reference point consumed by cv/occupancy.Occupancy.membership.
# Named bounding-box point for anchor membership: 'center' or 'bottom_center'.
# A box point is an image-space proxy, not a calibrated ground-plane position.
OCC_DEFAULT_ANCHOR = 'center'
# Consumed by cv/occupancy.Occupancy.membership.
# Uncertainty band = this fraction times min(box width, box height), in pixels.
# .02 is an initial engineering default, not a universal accuracy guarantee.
OCC_BOUNDARY_MARGIN_FRACTION = .02
# Consumed by cv/occupancy.Occupancy.membership and Settings.zone_policy.
# Boundary ambiguity may preserve a prior confirmed inside result for this many
# seconds after the last clear inside point. Ambiguity never renews that time.
# This initial default reuses the short hidden-person limit (currently 1.5 s).
OCC_BOUNDARY_MAX_SECONDS = HIDDEN_MAX_SECONDS

# Low-score recovery maximum 1-IoU cost; cv/tracker.ConfigurableBYTETracker.update second pass.
TRACK_SECOND_MATCH_MAX_COST = .5
# Unconfirmed new-track maximum 1-IoU cost; cv/tracker.ConfigurableBYTETracker.update.
TRACK_UNCONFIRMED_MATCH_MAX_COST = .7
# Duplicate tracked/lost box maximum 1-IoU cost; cv/tracker.remove_duplicate_stracks.
TRACK_DUPLICATE_MAX_COST = .15
# Maximum saved removed tracks; cv/tracker.ConfigurableBYTETracker.update.
TRACK_REMOVED_HISTORY_LENGTH = 1000
# Reference FPS for converting ByteTrack's buffer into source frames; cv/tracker.__init__.
TRACK_BUFFER_REFERENCE_FPS = 30.

# Backend operational and presentation configuration.
# Backend storage, request limits, and progress presentation tuning.
# SQLite's maximum busy-lock wait in seconds; database/repository.Repository.connection.
DATABASE_CONNECT_TIMEOUT_SECONDS = 10
# Minimum zero-padded daily run-number width; database/repository.Repository._allocate_name.
JOB_PUBLIC_RUN_NUMBER_WIDTH = 3
# Minimum upload ID/idempotency key characters; schemas/jobs.JobRequest and routes/jobs.create_job.
API_ID_MIN_LENGTH = 1
# Maximum upload ID/idempotency key characters; schemas/jobs.JobRequest and routes/jobs.create_job.
API_ID_MAX_LENGTH = 128
# Minimum requested simultaneous people count; schemas/jobs.JobRequest and frontend/app.py.
JOB_MIN_PEOPLE = 1
# Exclusive minimum gathering duration in video seconds; schemas/jobs.JobRequest.
JOB_MIN_THRESHOLD_SECONDS = 0
# Required polygon vertex count; schemas/jobs.JobRequest, cv/media_utils.validate_polygon, frontend/app.py.
JOB_POLYGON_POINT_COUNT = 4
# Upload copy buffer in bytes; routes/uploads.upload_video.
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
# Cloudinary resumable-upload chunk bytes; services/cloud_storage.CloudStorage.upload.
CLOUD_UPLOAD_CHUNK_BYTES = 6 * 1024 * 1024
# Initial diagnostics tail-read window in bytes; services/progress._last_record.
PROGRESS_LOG_INITIAL_READ_BYTES = 65536
# Largest diagnostics tail-read window in bytes; services/progress._last_record.
PROGRESS_LOG_MAX_READ_BYTES = 8 * 1024 * 1024
# Multiplicative expansion of diagnostics tail-read window; services/progress._last_record.
PROGRESS_LOG_READ_GROWTH_FACTOR = 2
# Decimal places in reported CV completion percent; services/progress.job_progress.
PROGRESS_PERCENT_DECIMALS = 1
# Historical overlap threshold only when an old job has no saved policy/threshold; routes/jobs.public_job.
# Keep this historical value independent of the current ZONE_OVERLAP_FRACTION tuning.
LEGACY_ZONE_OVERLAP_FRACTION = .7

# Frontend operational and presentation configuration.
# Frontend request, input, component rendering, and layout tuning.
# Each CSS block is an atomic stylesheet so every browser numeric layout value
# is editable here without splitting ordinary CSS into separate constants.
# Overall read/write/pool timeout seconds; frontend/api_client.py APIClient._request.
FRONTEND_API_REQUEST_TIMEOUT_SECONDS = 300
# TCP connection timeout seconds; frontend/api_client.py APIClient._request.
FRONTEND_API_CONNECT_TIMEOUT_SECONDS = 5
# Allowed browser upload extensions; frontend/app.py main.
FRONTEND_VIDEO_EXTENSIONS = ("mp4", "mov", "avi", "mkv", "webm", "m4v")
# Initial minimum people count; frontend/app.py main.
FRONTEND_COUNT_DEFAULT = 2
# People-count input increment; frontend/app.py main.
FRONTEND_COUNT_STEP = 1
# Smallest selectable duration in video seconds (backend separately accepts >0); frontend/app.py main.
FRONTEND_SECONDS_MIN = .001
# Initial alarm-rule duration in video seconds; frontend/app.py main.
FRONTEND_SECONDS_DEFAULT = 5.
# Duration input increment in video seconds; frontend/app.py main.
FRONTEND_SECONDS_STEP = .5
# Duration input display precision; frontend/app.py main.
FRONTEND_TIME_INPUT_DECIMALS = 3
# Alarm episode timestamps/durations display precision; frontend/app.py display_result.
FRONTEND_ALARM_TIME_DECIMALS = 3
# Submitted-region preview target width in CSS pixels; frontend/app.py processing_reference.
FRONTEND_REGION_PREVIEW_WIDTH = 500
# Submitted-region preview viewport cap and fitting; frontend/app.py processing_reference.
FRONTEND_REGION_PREVIEW_CSS = ".st-key-submitted-region img {max-height:40vh;width:auto!important;object-fit:contain;}"
# Canvas viewport cap, action spacing, button size/border and disabled opacity;
# frontend/annotation.py COMPONENT and frontend/annotation.js default component.
FRONTEND_ANNOTATION_CSS = """.zone-annotation {font-family:var(--st-font); color:var(--st-text-color);}
  canvas {max-width:100%; max-height:60vh; width:auto; height:auto; object-fit:contain; display:block; cursor:crosshair; touch-action:none;}
  .actions {display:flex; gap:12px; margin-top:12px;}
  button {font:inherit; padding:8px 14px; border:1px solid var(--st-border-color);
    border-radius:6px; background:var(--st-secondary-background-color);color:var(--st-text-color);cursor:pointer;}
  button:disabled {opacity:.5;cursor:default;}"""
# Shaded region colour/opacity; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_FILL_STYLE = "rgba(0,255,100,0.25)"
# Selected region outline colour; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_STROKE_STYLE = "#00ff66"
# Selected region outline width in canvas pixels; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_LINE_WIDTH = 3
# Corner-label font and pixel size; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_FONT = "18px sans-serif"
# Corner marker and label colour; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_POINT_STYLE = "#ffff00"
# Corner marker radius in canvas pixels; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_POINT_RADIUS = 5
# Corner-label horizontal offset in canvas pixels; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_LABEL_OFFSET_X = 8
# Corner-label vertical offset in canvas pixels; frontend/annotation.js draw via frontend/annotation.py annotate.
FRONTEND_ANNOTATION_LABEL_OFFSET_Y = 5
# Smallest fitted player height in CSS pixels; frontend/player.js resize via frontend/player.py result_player.
FRONTEND_PLAYER_MINIMUM_HEIGHT = 180
# Reserved viewport height in CSS pixels; frontend/player.js resize and frontend/player.py PLAYER CSS.
FRONTEND_PLAYER_VIEWPORT_MARGIN = 190
# Initial native video muted state; frontend/player.js default component via frontend/player.py result_player.
FRONTEND_PLAYER_MUTED = False
# Initial native video volume, in [0,1]; frontend/player.js default component via frontend/player.py result_player.
FRONTEND_PLAYER_VOLUME = 1.
# Player width limits, viewport cap, fitting, margins and background; frontend/player.py PLAYER.
# The viewport reserve is substituted from FRONTEND_PLAYER_VIEWPORT_MARGIN at render time.
FRONTEND_PLAYER_CSS = """.result-player {{width:100%;}}
  video {{display:block;max-width:100%;max-height:calc(100vh - {viewport_margin}px);object-fit:contain;margin:auto;background:#111;}}"""

# Minimum zero-padded saved frame filename width; cv/live_pipeline.process.
CAPTURE_FRAME_NUMBER_WIDTH = 4

# Numerical denominator floor for identity box areas; cv/identity_link.duplicate_extent/partial_crop_return.
IDENTITY_MIN_AREA = 1.
# Histogram normalization floor for empty colour crops; cv/identity_link.feature.
IDENTITY_HISTOGRAM_SUM_FLOOR = 1
# Sentinel time before any identity feature has been recorded; cv/identity_link.remember.
IDENTITY_NEVER_SEEN_TIME = -1e9
# Pipeline switches; services/pipeline.run enables supported continuity, readable labels and stable identity linking.
PIPELINE_EVIDENCE_MODE = True
PIPELINE_READABLE_LABELS = True
PIPELINE_STABLE_IDS = True
PIPELINE_WRITE_VIDEO = True
# Font identifier for legacy labels; cv/live_pipeline.process (OpenCV FONT_HERSHEY_SIMPLEX).
LEGACY_LABEL_FONT = 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Upload, job-output, SQLite, and worker-lock root; services and database/repository.py.
    data_dir: Path = ROOT / "data"
    # Binary MB limit enforced by routes/uploads.py and frontend/app.py.
    max_upload_mb: int = Field(default=50, ge=1)
    # Maximum decoded duration; services/validation.py and frontend/app.py.
    max_video_minutes: float = Field(default=20, gt=0)
    # Concurrent preflight decoder threads; services/validation.py.
    validation_workers: int = Field(default=1, ge=1, le=4)
    # Idle queue polling delay in seconds; workers/worker.py.
    worker_poll_seconds: float = Field(default=1, gt=0)
    # Maximum attempts including the first, for delivery retries; workers/worker.py.
    max_job_attempts: int = Field(default=3, ge=1, le=10)
    # Delay before retrying failed cloud delivery; workers/worker.py.
    retry_delay_seconds: float = Field(default=10, ge=0)
    # Age after which new submissions from an upload are refused; routes/jobs.py.
    upload_retention_hours: int = Field(default=24, ge=1)
    # FFmpeg executable for encoded alarm audio; workers/worker.py -> services/alarms.py.
    ffmpeg_path: str = "ffmpeg"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: SecretStr = SecretStr("")
    # Root prefix for date/job-isolated output asset names; services/cloud_storage.py.
    cloudinary_folder: str = "ppe-monitor"
    # Cloudinary requests and delivery checks timeout; services/cloud_storage.py.
    cloudinary_timeout_seconds: int = Field(default=120, ge=1)
    # CV model and thresholds: keep these together when tuning the pipeline.
    model_name: Literal["yolo26m.pt"] = MODEL_NAME
    # Local standard-model cache path; services/model_assets.py and services/pipeline.py.
    model_path: Path = ROOT / "models" / model_name
    # Select GPU when available for auto; services/pipeline.py.
    device: Literal["auto", "cpu", "cuda"] = "auto"
    # Detector input size; services/pipeline.py -> cv/live_pipeline.YoloDetector.
    image_size: int = Field(default=DETECTOR_IMAGE_SIZE, ge=32)
    # Use full decoded image instead of region crop, preserving detail subject to input-size cap; services/pipeline.py and cv/live_pipeline.py.
    full_frame_context: bool = False
    # Zone decision policy; services/pipeline.py -> cv/live_pipeline.py -> cv/occupancy.py.
    zone_membership_mode: Literal["anchor", "box_overlap"] = OCC_DEFAULT_MEMBERSHIP_MODE
    # Reference point used for anchor membership; services/pipeline.py -> cv/occupancy.py.
    zone_anchor: Literal["center", "bottom_center"] = OCC_DEFAULT_ANCHOR
    # Boundary band / smaller box dimension; services/pipeline.py -> cv/occupancy.py.
    zone_boundary_margin_fraction: float = Field(default=OCC_BOUNDARY_MARGIN_FRACTION, ge=0, le=1)
    # Maximum ambiguous-position hold seconds; services/pipeline.py -> cv/occupancy.py.
    zone_boundary_max_seconds: float = Field(default=OCC_BOUNDARY_MAX_SECONDS, ge=0)
    # Box-area fraction required inside polygon; services/pipeline.py -> cv/occupancy.py.
    overlap_fraction: float = Field(default=ZONE_OVERLAP_FRACTION, gt=0, le=1)
    # Supported short occlusion retention in seconds; services/pipeline.py -> cv/occupancy.py.
    max_hidden_seconds: float = Field(default=HIDDEN_MAX_SECONDS, gt=0)
    # Age limit for positive image continuity evidence; services/pipeline.py -> cv/visual_support.py.
    max_image_seconds: float = Field(default=IMAGE_MAX_SECONDS, gt=0)
    # Age limit for reliable full-body extent; services/pipeline.py -> cv/occupancy.py.
    max_body_reference_seconds: float = Field(default=BODY_MAX_REFERENCE_SECONDS, gt=0)
    # Largest accepted consecutive timestamp gap; services/validation.py and cv/live_pipeline.py.
    max_frame_gap_seconds: float = Field(default=VIDEO_MAX_FRAME_GAP_SECONDS, gt=0)

    @property
    def zone_policy(self) -> dict:
        """Saved with each accepted job so later config edits cannot change its policy."""
        return dict(mode=self.zone_membership_mode, anchor=self.zone_anchor,
                    boundary_margin_fraction=self.zone_boundary_margin_fraction,
                    boundary_max_seconds=self.zone_boundary_max_seconds,
                    overlap_fraction=self.overlap_fraction)

    @property
    def max_video_seconds(self) -> float:
        return self.max_video_minutes * 60

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    def prepare_directories(self) -> None:
        for name in ("uploads", "jobs"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
