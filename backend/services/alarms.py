"""Add audio from notebook events; do not infer or change alarm decisions."""
import math
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import av
from backend.core import config as cfg

from .media import video_endpoint


def build_intervals(report, endpoint):
    if not math.isfinite(endpoint) or endpoint <= 0:
        raise ValueError("Output video duration must be finite and positive.")
    resets = sorted(report["resets"])
    intervals = []
    n, seconds = report["N"], report["T"]
    condition = (f"Estimated occupancy stayed at least {n} for more than {seconds:g} video seconds; "
                 f"at least {n} people were directly observed at trigger. "
                 f"Alarm remains active until estimated occupancy falls below {n}.")
    policy = report.get("zone_policy")
    if policy:
        if policy["mode"] == "anchor":
            anchor = policy.get("anchor", "center").replace("_", " ")
            condition += f" Zone membership uses the box {anchor}, with bounded boundary uncertainty."
        else:
            condition += f" Zone membership requires {policy.get('overlap_fraction', cfg.LEGACY_ZONE_OVERLAP_FRACTION):g} of box area inside."
    for index, event in enumerate(report["events"], 1):
        start = float(event["seconds"])
        reset = next((r for r in resets if r > start), None)
        end = min(float(reset), endpoint) if reset is not None else endpoint
        if start < 0 or end <= start:
            raise ValueError("Alarm trigger is outside the output video.")
        intervals.append(dict(index=index, start_seconds=start, end_seconds=end,
                              duration_seconds=end-start,
                              end_reason="condition_invalidated" if reset is not None and reset <= endpoint else "video_ended",
                              observed_at_trigger=event["observed"], estimated_at_trigger=event["estimated"],
                              condition=condition))
    return intervals


def add_alarm_audio(source, target, intervals, endpoint, ffmpeg_path="ffmpeg"):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Per-sample gating, rather than wall-clock sound or one beep per frame.
    gates = "+".join(f"(gte(t,{a['start_seconds']:.9f})*lt(t,{a['end_seconds']:.9f}))" for a in intervals) or "0"
    expression = f"aevalsrc=exprs='{cfg.ALARM_AMPLITUDE}*sin(2*PI*{cfg.ALARM_FREQUENCY_HZ}*t)*({gates})':s={cfg.ALARM_SAMPLE_RATE}:d={endpoint:.9f}[alarm]"
    temporary = target.with_name(target.stem + ".pending.mp4")
    with tempfile.TemporaryDirectory(dir=target.parent) as staging:
        media_source = source
        if endpoint > video_endpoint(source) + cfg.ALARM_ENDPOINT_EPSILON_SECONDS:
            media_source = Path(staging) / "video.mp4"
            _hold_final_frame(source, media_source, endpoint)
        script = Path(staging) / "alarm.ffscript"
        script.write_text(expression)
        try:
            subprocess.run([ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(media_source), "-filter_complex_script", str(script),
                            "-map", "0:v:0", "-map", "[alarm]", "-c:v", "copy",
                            "-c:a", cfg.ALARM_AUDIO_CODEC, "-b:a", cfg.ALARM_AUDIO_BITRATE, "-movflags", "+faststart", str(temporary)],
                           check=True, capture_output=True, timeout=max(cfg.ALARM_MIN_TIMEOUT_SECONDS, endpoint * cfg.ALARM_TIMEOUT_DURATION_MULTIPLIER))
            temporary.replace(target)
        except (subprocess.SubprocessError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Could not add alarm audio; check FFmpeg installation and local storage.") from exc
    return target


def _hold_final_frame(source, target, endpoint):
    """Restore final-frame hold during packaging; copy encoded pixels and PTS."""
    with av.open(str(source)) as video:
        stream = video.streams.video[0]
        stamps = (packet.pts for packet in video.demux(stream) if packet.pts is not None)
        first, last = None, None
        for stamp in stamps:
            first = stamp if first is None else min(first, stamp)
            last = stamp if last is None else max(last, stamp)
        if last is None:
            raise ValueError("No annotated video packets.")
        base = stream.time_base
    end = first + round(Fraction(str(endpoint)) / base)
    with av.open(str(source)) as video, av.open(str(target), "w", format="mp4") as output:
        stream = video.streams.video[0]
        copied = output.add_stream_from_template(stream)
        copied.time_base = base
        for packet in video.demux(stream):
            if packet.dts is None:
                continue
            if packet.pts == last:
                packet.duration = max(packet.duration, end - last)
            packet.stream = copied
            output.mux(packet)
