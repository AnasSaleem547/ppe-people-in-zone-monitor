"""Observe the notebook's existing diagnostics; never alter the CV execution."""
import json
from pathlib import Path

from backend.core import config as cfg


def _last_record(path):
    try:
        with path.open('rb') as log:
            log.seek(0, 2)
            end = log.tell()
            size = min(cfg.PROGRESS_LOG_INITIAL_READ_BYTES, cfg.PROGRESS_LOG_MAX_READ_BYTES, end)
            while size:
                log.seek(end-size)
                lines = log.read(size).split(b'\n')
                # Ignore the final possibly unflushed/incomplete record.
                for line in reversed(lines[:-1]):
                    try:
                        row = json.loads(line)
                        if isinstance(row.get('frame'), int) and row['frame'] >= 0:
                            return row
                    except (ValueError, AttributeError, UnicodeError):
                        continue
                if size == end or size >= cfg.PROGRESS_LOG_MAX_READ_BYTES:
                    break
                size = min(end, cfg.PROGRESS_LOG_MAX_READ_BYTES, size*cfg.PROGRESS_LOG_READ_GROWTH_FACTOR)
    except OSError:
        pass
    return None


def job_progress(job, upload):
    total = upload['metadata'].get('validation', {}).get('frames')
    checkpoint = job['checkpoint']
    report = checkpoint.get('report')
    frames, seconds = 0, 0.
    if report:
        frames = report.get('frames', total or 0)
        seconds = report.get('last_video_seconds', 0.)
    elif checkpoint.get('cv_root'):
        logs = list(Path(checkpoint['cv_root']).glob('gathering_*/diagnostics.jsonl'))
        for path in logs:
            row = _last_record(path)
            if row and row['frame'] + 1 > frames:
                frames, seconds = row['frame'] + 1, row.get('video_seconds', 0.)
    if job['status'] == 'succeeded' and total:
        frames = total
    return dict(frames_analyzed=frames, total_frames=total,
                cv_percent=round(min(100., 100*frames/total), cfg.PROGRESS_PERCENT_DECIMALS) if total else None,
                video_seconds=seconds)
