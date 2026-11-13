import subprocess

import av
import numpy as np


def report():
    return dict(N=2, T=1, overlap_fraction=.7,
                events=[dict(seconds=.5, observed=2, estimated=2), dict(seconds=1.5, observed=2, estimated=3)],
                resets=[.2, 1.0])


def test_intervals_ignore_pretrigger_resets_and_close_last_alarm_at_video_end():
    from services.alarms import build_intervals
    alarms = build_intervals(report(), 2.5)
    assert len(alarms) == 2
    assert (alarms[0]["start_seconds"], alarms[0]["end_seconds"], alarms[0]["end_reason"]) == (.5, 1., "condition_invalidated")
    assert (alarms[1]["start_seconds"], alarms[1]["end_seconds"], alarms[1]["end_reason"]) == (1.5, 2.5, "video_ended")
    assert alarms[0]["observed_at_trigger"] == 2
    assert "more than 1" in alarms[0]["condition"]
    assert "estimated" in alarms[0]["condition"]


def test_sound_intervals_keep_video_packets_and_frame_timestamps(video_factory, tmp_path):
    from services.alarms import add_alarm_audio, build_intervals
    from services.media import video_endpoint
    source = video_factory()
    target = tmp_path / "with-alarm.mp4"
    endpoint = video_endpoint(source)
    assert abs(endpoint - 2.5) < .02
    add_alarm_audio(source, target, build_intervals(report(), endpoint), endpoint)
    def stamps(path):
        with av.open(str(path)) as c:
            return [float(f.time) for f in c.decode(video=0)]
    assert stamps(source) == stamps(target)
    def hashes(path):
        return subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_packets", "-show_entries", "packet=data_hash", "-show_data_hash", "sha256",
            "-of", "csv=p=0", str(path)])
    assert hashes(source) == hashes(target)
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(target), "-map", "0:a:0",
                                  "-f", "f32le", "-ac", "1", "-ar", "48000", "pipe:1"])
    samples = np.frombuffer(raw, np.float32)
    def rms(start, end):
        return float(np.sqrt(np.mean(samples[int(start*48000):int(end*48000)] ** 2)))
    assert rms(.65, .85) > .05
    assert rms(1.65, 1.85) > .05
    assert rms(.15, .35) < .001
    assert rms(1.15, 1.35) < .001


def test_no_alarm_produces_silent_track_without_shortening_video(video_factory, tmp_path):
    from services.alarms import add_alarm_audio
    from services.media import video_endpoint
    source = video_factory()
    target = tmp_path / "silent.mp4"
    endpoint = video_endpoint(source)
    add_alarm_audio(source, target, [], endpoint)
    with av.open(str(target)) as c:
        assert len(c.streams.audio) == 1
    assert abs(video_endpoint(target) - endpoint) < .001


def test_audio_package_holds_last_frame_until_validated_source_endpoint(tmp_path):
    from fractions import Fraction
    from services.cv.media_utils import AnnotatedVideo
    from services.alarms import add_alarm_audio
    from services.media import video_endpoint
    source = tmp_path / "notebook.mp4"
    writer = AnnotatedVideo(str(source), 160, 120)
    for i in range(12):
        writer.write(np.full((120,160,3), 40, np.uint8), Fraction(i, 5))
    writer.close()
    assert video_endpoint(source) == 2.233333
    target = tmp_path / "aligned.mp4"
    add_alarm_audio(source, target, [dict(start_seconds=.4, end_seconds=2.4)], 2.4)
    assert abs(video_endpoint(target) - 2.4) < .001
    def frames(path):
        with av.open(str(path)) as c:
            return [(float(f.time), f.to_ndarray()) for f in c.decode(video=0)]
    original, final = frames(source), frames(target)
    assert [x[0] for x in original] == [x[0] for x in final]
    for a, b in zip(original, final):
        np.testing.assert_array_equal(a[1], b[1])
