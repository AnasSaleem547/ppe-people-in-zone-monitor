# People in Zone Monitor

FastAPI + Streamlit around `PPE_YOLO_continuity_finalister.ipynb`. The original
notebook is untouched. The seven Python modules from cells 3–9 live in
`services/cv/`; only sibling imports changed to package-relative imports.
`provenance/notebook_cells.json` contains the source snapshot and notebook hash.

This detects **people**, not helmets/vests. It counts occupancy, not a fixed set
of N identities. The existing detector, custom ByteTrack tracking, concealment
techniques, identity linking, rendering, frame timestamps and alarm policy remain
in those modules. Internal thresholds stay frozen there. The notebook's exposed
settings are in `config.py`. Changing them can change detection behavior.

## Start locally

Use Python 3.12 or 3.13, FFmpeg/FFprobe and the notebook's PyTorch installation.
The prepared `.venv` reuses this machine's existing PyTorch and CV packages.
To recreate it on this machine:

```bash
cd /home/anas/Desktop/tezeract/Probation/PPE_N_Person_X_Zone_T_Seconds/codebase
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

For an independent machine, install the appropriate PyTorch CPU/CUDA build
first, then the requirements. Do not silently replace model weights or lower
image size to make a weaker machine faster. `MODEL_PATH` defaults to the existing
`yolo26m.pt` in the parent folder; set it to the exact weights on another machine.
Model weights are not committed. Keep the same dependency versions for comparisons.

Run these in **three terminals**, each in `codebase`:

```bash
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010 --workers 1
```

```bash
.venv/bin/python worker.py
```

```bash
.venv/bin/python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. API documentation: http://127.0.0.1:8010/docs.
Port 8010 avoids a service already using port 8000 on this machine. If changing
the API port, update `API_BASE_URL` in `.env` as well.

Use one API process and one worker on one host, sharing the same local `DATA_DIR`.
Do not put the SQLite database on a network filesystem. The worker rejects a
second worker using the same data folder. Ctrl+C lets the worker finish its
current job before exiting. A forced exit requeues interrupted jobs at restart.
Completed CV/audio checkpoints are reused; interrupted inference starts again.

## Configuration and credentials

The supplied Cloudinary credentials are already copied **verbatim** into the
local `.env` file. It has owner-only permissions and is ignored by Git. No
Cloudinary secret is included in committed files or API responses. When moving
the app, transfer that file privately or set its environment variables.

Infrastructure environment variables:

- `DATA_DIR`: database, uploaded files and per-job artifacts; defaults to `codebase/data`.
- `API_BASE_URL`: Streamlit's backend address; local default uses port 8010.
- `MAX_UPLOAD_MB`: default 200, applied by both UI and backend.
- `VALIDATION_WORKERS`: default 1, separate from the CV worker.
- `UPLOAD_RETENTION_HOURS`: new processing submissions expire after 24 hours by
  default. This does not automatically delete files or existing jobs.
- `WORKER_POLL_SECONDS`: default 1; worker queue check interval.
- `MAX_JOB_ATTEMPTS`, `RETRY_DELAY_SECONDS`: defaults 3 and 10 for cloud delivery retries.
- `FFMPEG_PATH`: defaults to `ffmpeg` on PATH.
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: backend only.
- `CLOUDINARY_FOLDER`, `ENVIRONMENT`: asset naming root and environment.
- `CLOUDINARY_TIMEOUT_SECONDS`: default 120 for provider and delivery requests.
- `MODEL_PATH`, `DEVICE`: exact model path and `auto`/`cpu`/`cuda`.

The remaining CV defaults match cell 2. Cell 13's `evidence_mode`,
`readable_labels`, `stable_ids`, and video writing are explicitly enabled by the
adapter. CPU threads follow the notebook's limit; CUDA out-of-memory initialization
falls back to the same model and image size on CPU.

## User flow and API contract

1. Select a video and click **Get first frame**. The transfer must finish before
   the API can return its preview. Decoding only the beginning makes preview
   extraction quick; it does not establish that the entire file is readable.
2. Click four corners in order and inspect the shaded polygon. This
   supports valid concave four-sided polygons as in the notebook. The frontend
   maps actual displayed/preview dimensions to original decoded coordinates;
   the backend applies the notebook's own polygon validator.
3. Enter N and T, review the shaded region, then click **Confirm region & process**. A background full-decode check runs while
   annotation takes place. A pending submission waits for that check; a failure
   stops the job before inference. Validation never rewrites detector input.
4. Check status manually for any video. Known durations below 30 seconds enable
   seven-second checks while the Streamlit session is active. Video length does
   not predict queue or processing time. Unknown duration uses manual checks.
5. On success, the video is immediately available. The marked first frame is in
   **Submitted region (reference)**. The player fits both available width and
   screen height, preserving the video aspect ratio. Click **Play with sound**.
   Alarm summaries give trigger/end seconds and their condition. The run ID is
   also in the page URL and can be loaded from the sidebar after a browser refresh.

Exactly three application routes, without a version prefix:

- `POST /api/uploads`: multipart field `file`; returns 201, `upload_id`, inline
  JPEG `first_frame`, original and preview dimensions, provisional duration and
  validation status. The raw video is saved on disk, not embedded in the response.
- `POST /api/jobs`: JSON `upload_id`, `n_people`, `threshold_seconds`, and `polygon`
  containing four `[x,y]` points in original coordinates. Returns 202 and a job.
  Optional `Idempotency-Key` makes retries reuse the same job; changed inputs
  with that key return 409. Streamlit sends a stable key automatically.
- `GET /api/jobs/{job_id}`: returns status, phase, validation state, marked
  `region_preview`, submitted polygon, errors and completed result when ready.
  It performs no inference. The browser fetches completed video from Cloudinary.

Job states: `waiting_validation`, `queued`, `processing`, `adding_audio`,
`uploading`, `succeeded`, `failed`. Cloud H.264 preparation is part of uploading.
A 202 response means accepted; only an actually claimed job says processing started.
OpenAPI/Swagger documentation routes are provided by FastAPI in addition to these
three application routes. Internal files and secrets are not served as static data.

## Alarm policy and audio

The unchanged timer uses video timestamps, not computer processing time:
estimated occupancy must stay at least N for **strictly more than T** seconds;
triggering requires N directly observed people. After triggering, sound continues
until the notebook's estimated count falls below N. Concealment can therefore
keep an alarm active. Another qualifying period can trigger another episode.

The audio service reads recorded trigger/reset events. Pre-trigger resets are
ignored. An active final episode ends at the decoded source video's endpoint and is
labelled `video_ended`, not a count invalidation. FFmpeg copies the annotated video
packets and adds a generated 880 Hz alarm track over silence. Original source
audio is not retained, matching the notebook's video-only writer. Zero alarms
produce silence. AAC audio encoding can smear edges by a small fraction of a
second; playback sound also depends on browser/device volume and mute settings.
The notebook's nominal encoder rate can shorten its final frame's hold. The audio
packaging step restores that hold to the validated source endpoint, without
changing encoded pixels or frame timestamps. If the source omits final-frame
duration, validation uses its last frame spacing or nominal rate as a fallback.

Cloudinary assets use:

```text
ppe-monitor/{environment}/{YYYY}/{MM}/{job_id}/annotated
```

The date uses UTC. No filename extension is put in the public ID. The upload uses
`resource_type=video`, `overwrite=False`, matching `asset_folder`, and synchronous
eager H.264 MP4 generation. The actual returned derivative URL includes `vc_h264`
between `/upload/` and the version. A delivery HEAD check must return video before
the job succeeds. Retries reuse the same asset name and saved local CV/audio.
Cloudinary's delivery conversion may re-encode video even though the local audio
step does not. Normal upload URLs are accessible to people who have the link;
this local prototype has no user-account isolation. No cloud assets are deleted
automatically.

## Modules and validation

- `main.py`, `routes/`, `schemas.py`: API entry point and contracts.
- `repository.py`: SQLite job/validation transactions, claim and recovery.
- `worker.py`: serial CV/audio/upload orchestration and cloud retries.
- `services/cv/`: notebook modules; see provenance snapshot for exact source.
- `services/pipeline.py`: notebook settings, initialization and processing adapter.
- `services/media.py`, `validation.py`: preview, marked region, preflight and video endpoint.
- `services/alarms.py`, `cloud_storage.py`: independent audio and cloud delivery.
- `frontend/`: Streamlit screens, API client, annotation JS component and state rules.

Run the full local suites:

```bash
.venv/bin/python -m pytest -q
node --test tests/*.test.mjs
```

Tests cover source preservation, strict timer/reset behavior, rendered-frame
agreement with the snapshot, recorded-detector processing, queue persistence,
validation gating, API contracts, cloud delivery handling and real FFmpeg audio
intervals/video packet preservation. Provider HTTP and model inference are
isolated in unit tests; separately recorded smoke checks exercise the real model,
browser and cloud. See `docs/validation.md` for measured results and limits.

Agreement on test fixtures does not establish unchanged accuracy on all videos.
The decoder may conceal some damaged input rather than report it. Accepted jobs
survive application restarts only while the local database and artifacts remain
available. There is no exactly-once execution claim across crashes or storage loss.
Keep runtime/version changes deliberate and compare representative videos before
using a new environment for decisions.

## Filename-based run names and sound controls (2026-11-13 update)

New uploads retain their original filename as metadata. `Front Door.MP4` produces
public run names such as `front-door-run-0001`; the suffix distinguishes runs
within the retained database. Public names are stored once and indexed uniquely,
so maintenance does not recalculate existing links. The original random IDs stay
internal for artifact isolation and old links continue to work. Files uploaded
before filenames were retained use `video-run-0001` style names; their original
filename cannot be recovered from the saved metadata. Names, like jobs, depend
on keeping this database. Filenames are never used as local filesystem paths.

The custom Streamlit v2 result player has explicit **Play with sound** (unmutes
and restores full player volume) and **Test sound**. If the video audio stays
silent in your browser, select **Browser tone (fallback)** then click **Play
with sound**. It uses browser-generated 880 Hz audio only during the returned
alarm intervals, pauses during buffering/seek/pause, and mutes the original track
to avoid double sound. The downloaded/cloud video still contains its own audio.
Page updates pause playback when tearing down the audio controller; resume with
Play with sound. No page can override a muted browser tab or device volume.

The reported N=2/T=5 run's local and Cloudinary audio were decoded directly:
a one-second sample at video second 7 contained an 880 Hz tone around -15 dBFS,
while samples at seconds 1 and 20 were silent. This rules out a silent delivered
track on that run; the user's exact browser silence was not reproduced. The
previous `muted=false` test did not prove speaker output. This update supplies
explicit controls and an independent browser-tone fallback. Live browser
verification of this revision was blocked because local browser access was
disabled in Work settings. Renderer tests exercise native sound enablement,
interval gating, pause/buffering behavior, cleanup and portrait/landscape sizing.
