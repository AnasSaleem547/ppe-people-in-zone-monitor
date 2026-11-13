# People in Zone Monitor

FastAPI + Streamlit around `PPE_YOLO_continuity_finalister.ipynb`. The original
notebook is untouched. Its seven Python modules from cells 3–9 live under
`services/cv/`, with only package-relative imports changed. The source snapshot
and notebook hash are in `provenance/notebook_cells.json`.

## Run locally

From this folder, in three terminals:

```bash
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010 --workers 1
```

```bash
.venv/bin/python worker.py
```

```bash
.venv/bin/python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Open [Streamlit](http://127.0.0.1:8501) or [API documentation](http://127.0.0.1:8010/docs).
Port 8010 avoids another local service on port 8000. One API process and one
worker share the same local `DATA_DIR`; network filesystem/multi-host operation
is outside this version's scope. The worker lock prevents two workers using
that data folder. Graceful shutdown finishes the current job; interrupted
inference starts again on restart. Completed CV/audio checkpoints are reused.

## Recreate the environment

```bash
conda env create -f environment.yml
conda activate ppe-monitor
```

Then use `python` instead of `.venv/bin/python` in the commands above.
`environment.yml` pins Python 3.13.12, pip 25.3, upstream FFmpeg 8.0.1 and 75
Python packages from the actual installed dependency graph, including CPU
PyTorch 2.11.0+cpu and torchvision 0.26.0+cpu. CPU wheels use the official
PyTorch wheel index. It describes this Linux CPU runtime; it is not a tested
CUDA environment. YAML parsing and comparison to installed package metadata
passed; a fresh Conda environment has not been created. Conda's FFmpeg build
may differ from this machine's Ubuntu build despite matching upstream version.

The existing `.venv` uses this machine's Python/CV packages. For that installation:

```bash
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

`MODEL_PATH` defaults to `yolo26m.pt` in the parent folder. On another machine,
provide the exact model weights yourself. Weights are not committed. Keep
runtime changes deliberate: matching source does not establish equal accuracy
across hardware, package versions, or unseen videos.

## Upload limits and configuration

All settings are declared in `config.py` (`Settings`):

- `max_upload_mb = 50`: shared by Streamlit and backend. Here MB means
  1,048,576 bytes, matching Streamlit, so the limit is 52,428,800 bytes.
- `max_video_minutes = 20`: `max_video_seconds` derives the 1,200-second limit.
  Reported duration is checked during preview; full decoding checks actual
  timestamps and final-frame duration before inference, including recordings
  with missing/incorrect duration metadata. Over-limit videos are rejected.
- `data_dir`: database/uploads/job artifacts; defaults to `codebase/data`.
- `api_base_url`: defaults to `http://127.0.0.1:8010`.
- `validation_workers = 1`, `worker_poll_seconds = 1`.
- `upload_retention_hours = 24`: limits new submissions, not automatic deletion.
- `max_job_attempts = 3`, `retry_delay_seconds = 10`: cloud delivery retry settings.
- `short_video_seconds = 30`, `status_poll_seconds = 7`.
- `ffmpeg_path`, Cloudinary credentials/folder/environment/timeouts, model/device,
  and notebook-exposed CV settings.

Environment variables can override settings. The local `.env` contains the
supplied Cloudinary credentials verbatim, is ignored by Git, and has owner-only
permissions. Upload limits are not duplicated in `.env`. Do not expose the
secret in frontend code, API responses or logs.

## User flow

1. Upload a video and request its first frame. Upload must finish before the
   preview is available. The beginning being readable does not validate the rest.
2. Draw four ordered corners. Review the shaded polygon and N/T settings, then
   click **Confirm region & process**. Concave valid quadrilaterals are supported.
   The frontend converts preview coordinates to original decoded coordinates;
   the backend uses the notebook's polygon validator.
3. Background validation runs while the user annotates. Jobs wait for it to
   succeed; failures stop inference. Original uploaded bytes feed CV processing.
4. **Processing status** shows the exact uploaded filename and submitted region,
   followed by dynamic progress. Refresh manually for any recording. Videos
   with known duration below 30 seconds check every seven seconds while the
   Streamlit session is active. Longer or unknown-duration videos use manual
   checks. Length is not an estimate of processing time.
5. Progress shows analysed frames and CV percentage based on the fully decoded
   input count. It reads the notebook's existing buffered diagnostics, so it
   can lag slightly. It is not a promise of instantaneous tracking. A 100% CV
   count means frame analysis has finished, not that audio or upload is ready.
   Those phases and final success are shown separately.
6. Completed video appears immediately with native playback/sound controls.
   Portrait and landscape media fit screen width and height without stretching.
   **Watch output video in a new tab** opens the Cloudinary file. Alarm summaries
   show trigger/end times, durations and conditions. There is no second region
   confirmation or extra sound toolbar.

**Resume a run** reopens an accepted job after closing/refreshing the page,
without rerunning CV. Use the ID from the page's `?job=` URL. The displayed
`job_name` is exactly the uploaded basename, including spaces, case and extension.
Internal `run-0001`-style IDs distinguish duplicate names; storage/cloud isolation
continues to use random internal IDs. Filenames never become filesystem paths.

## API contract

Exactly three application APIs, without a `v1` prefix:

- `POST /api/uploads`: multipart `file`; returns 201 with `upload_id`, inline
  JPEG `first_frame`, dimensions, provisional duration and validation status.
- `POST /api/jobs`: JSON `upload_id`, positive integer `n_people`, finite positive
  `threshold_seconds`, and four `[x,y]` polygon points in original coordinates.
  Returns 202. Optional `Idempotency-Key` returns the same job on network retries;
  changed inputs with that key return 409. Streamlit sends this key automatically.
- `GET /api/jobs/{job_id}`: returns `job_name`, status, phase, queue position,
  `progress` (`frames_analyzed`, `total_frames`, `cv_percent`, `video_seconds`),
  submitted region, errors and completed result. GET performs no inference.

States: `waiting_validation`, `queued`, `processing`, `adding_audio`, `uploading`,
`succeeded`, `failed`. H.264 cloud preparation is included in uploading. A 202
response means accepted; processing starts only after the worker claims the job.
OpenAPI/Swagger adds documentation routes. Internal files and credentials are
not served as static data. This local prototype has no per-user account isolation.

## CV policy and output media

The model detects people, not helmets/vests. It counts occupancy, not a fixed
set of N identities. Model weights, crop calculations, tracking, concealment,
identity linking, rendering and timestamp policy remain in the original modules.
Cell 13 flags `evidence_mode`, `readable_labels`, `stable_ids` and video writing
are explicitly enabled. Initialization retains the same model and image size
when falling back from CUDA out-of-memory to CPU.

Estimated occupancy must remain at least N for strictly more than T video
seconds; a new alarm requires N direct observations. It remains active until
estimated occupancy falls below N, including supported concealment. Later periods
can trigger further episodes. Audio follows these saved events/reset times.
Pre-trigger resets are ignored. A final active episode closes at the decoded
source endpoint, labelled as video ended in the result data.

FFmpeg copies annotated video packets and adds an 880 Hz AAC alarm track over
silence; original input audio is not retained, matching the notebook writer.
The packaging step can restore the final frame's hold to the validated source
endpoint without changing encoded pixels or frame timestamps. Missing final-frame
duration falls back to last spacing or nominal rate. Audio encoding can slightly
smear edges/pad duration; actual sound depends on player, browser and device volume.

Cloud assets use `ppe-monitor/{environment}/{YYYY}/{MM}/{internal_job_id}/annotated`
with UTC dates, no extension in public ID, matching asset folder, `overwrite=False`,
and eager H.264 MP4 conversion. A delivery HEAD check must return video content
before success. Cloud conversion may re-encode. URLs include `vc_h264` after
`/upload/`; the browser fetches video directly. A public upload URL is accessible
to anyone with its link. No cloud assets or local artifacts are automatically deleted.

## Database reset and verification

The requested fresh start resets only the SQLite job/upload registry. A verified
SQLite backup is kept under `data/backups`. Existing media files and cloud assets
remain. Old run links are no longer valid in the fresh registry. Recovering old
jobs requires restoring the backup with services stopped.

```bash
.venv/bin/python -m pytest -q
node --test tests/*.test.mjs
```

Tests cover notebook source preservation, timers, rendering, video/audio timing,
queue/validation, duration/size limits, filename display, progressive GET responses,
UI reference ordering and player sizing. See `docs/validation.md` for dated
measurements and limitations. Buffered diagnostics do not imply finished encoding.
Decoders can conceal some corruption. Job persistence depends on retaining the
local database and media. There is no exactly-once execution guarantee across
crashes or storage loss. Historical test counts and the earlier fallback sound
controls in that document describe earlier revisions, not current UI behavior.
