"""Add audio from notebook events; do not infer or change alarm decisions."""
import math
import subprocess
import tempfile
from pathlib import Path


def build_intervals(report, endpoint):
    if not math.isfinite(endpoint) or endpoint <= 0:
        raise ValueError("Output video duration must be finite and positive.")
    resets = sorted(report["resets"])
    intervals = []
    n, seconds = report["N"], report["T"]
    condition = (f"Estimated occupancy stayed at least {n} for more than {seconds:g} video seconds; "
                 f"at least {n} people were directly observed at trigger. "
                 f"Alarm remains active until estimated occupancy falls below {n}.")
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
    expression = f"aevalsrc=exprs='0.25*sin(2*PI*880*t)*({gates})':s=48000:d={endpoint:.9f}[alarm]"
    temporary = target.with_name(target.stem + ".pending.mp4")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ffscript", dir=target.parent) as script:
        script.write(expression)
        script.flush()
        try:
            subprocess.run([ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(source), "-filter_complex_script", script.name,
                            "-map", "0:v:0", "-map", "[alarm]", "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(temporary)],
                           check=True, capture_output=True, timeout=max(120, endpoint * 2))
            temporary.replace(target)
        except (subprocess.SubprocessError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Could not add alarm audio; check FFmpeg installation and local storage.") from exc
    return target
