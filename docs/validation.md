# Verification recorded on 2026-11-13

## Automated checks

- `python -m pytest -q`: 33 tests passed (full codebase suite).
- `node --test tests/annotation.test.mjs`: 3 tests passed.
- `python -m pip check`: no broken requirements.
- Requirements install dry-run resolved against the prepared environment.
- Seven extracted CV module bodies match the attached notebook snapshot exactly,
  after reversing the authorized package-relative import changes.
- The attached notebook's current SHA-256 still matches the hash captured before
  implementation. The notebook itself was not edited.
- A failing integration test reproduced the independent review's finding: an
  accepted idempotency key returned 410 after upload expiry. The test now passes
  for identical retries, changed-input conflicts and rejection of new expired
  submissions. A newly constructed worker also reuses persisted checkpoints.

## What the real-model comparison measured

Input: a synthetic 12-frame, 5-fps clip made by repeating the existing
`tests/fixtures/doorway_731.jpg` photograph from the parent project. It is
1280×720, with 2.4 seconds of source video. This is an integration fixture,
not a labelled detection-accuracy benchmark or natural moving footage.

The model was the existing parent-directory `yolo26m.pt`, running on CPU with
PyTorch 2.11.0+cpu, Ultralytics 8.4.37 and PyAV 19.0.2. The run used N=1,
T=0.2, the notebook's 0.70 overlap, cropped inference, and all three cell-13 flags.

The original notebook modules were separately loaded, with their original bare
imports, and executed on the same uploaded bytes and submitted polygon. Compared
with the wrapped CV output, all 12 diagnostic rows matched, including counts,
track data, raw detector outputs and timer state. Trigger events and resets
matched. Every decoded annotated frame matched pixel-for-pixel before the audio
packaging and Cloudinary delivery steps.

Those measurements establish agreement on this fixture in this CPU environment.
They do not establish accuracy on unseen recordings or equivalence on other
hardware/library versions.

## Browser and Cloudinary checks

A real Chromium browser completed upload, four-point drawing, confirmation, N/T
entry and submission. Seven-second polling reached completion without a manual
status click. The result showed the marked first frame. No video element was
present before region verification; after checking the region, the browser
loaded and played the Cloudinary URL with `muted=false`. No browser page errors
were recorded. This verifies media playback, not that a human heard the sound.

Final smoke job: `8d56cc4df0b440d1bba454f8ad4e88da`.

One alarm episode was reported: start 0.4 seconds, end 2.4 seconds, ending because
the video ended. The detector reported six observed people at trigger; no
ground-truth count was measured here.

The uploaded video was retrieved through the returned `vc_h264` delivery URL.
A HEAD check returned video content and the browser reached readyState 4, advanced
past 0.5 seconds, and reported 1280×792 pixels, including the unchanged 72-pixel
annotation footer. FFprobe confirmed H.264 video and AAC audio on Cloudinary.

## Final-frame timing finding

For this 5-fps fixture, the notebook's writer produced 12 correctly timestamped
frames, last timestamp 2.2 seconds, but used a final hold of 1/30 second:
2.233333 seconds total. Cloudinary's H.264 conversion gave that last frame its
5-fps hold again, reaching 2.4 seconds. This finding was measured on this fixture;
it is not assumed to describe all video formats.

A failing test first captured the resulting packaging mismatch. The post-CV
packaging now retains decoded source endpoint metadata and extends only the
last encoded frame's duration when necessary. On the final run, packaged video
and audio both measured 2.4 seconds. Cloudinary video measured 2.4 seconds;
AAC padding made its audio/container measure 2.411 seconds. The 11-ms difference
is encoding padding; the reported condition interval remains [0.4, 2.4).

Tests check unchanged decoded pixels and frame timestamps after that adjustment.
Separate FFmpeg tests verify encoded packet hashes, sound inside alarm intervals,
silence between intervals, and an all-silent no-alarm result. Exact audible edges
are subject to audio encoding and playback behavior.

## Local operation and limits

API: `http://127.0.0.1:8010`; UI: `http://127.0.0.1:8501`. Port 8000 was already
in use by another service and was not disturbed. One API process and one CV
worker share local SQLite and artifacts. No multi-host or GPU deployment was
tested. Old historical suites in the parent directory were not modified or
represented as passing; the full new codebase suite was run.

The exact supplied Cloudinary values are in local ignored `.env` with mode 0600.
A scan of Git-tracked files found no secret value. Two development smoke assets
were uploaded under separate job IDs; no unrelated assets were changed or deleted.
No remote repository was configured or pushed. Implementation commits remain in
the new local `codebase` repository on `feat/fastapi-streamlit`.

## UI revision verification

Current suite: 36 Python tests and 8 JavaScript tests pass. Original counts above
are historical. Source-preservation tests still pass. New tests first failed for
filename run naming, redundant result confirmation, database row relocation, and
a rerender leaving muted fallback playback without sound. These now pass. The
player renderer is exercised with controlled media/AudioContext objects; these
checks do not establish physical speaker output. Live UI inspection was blocked
by Work settings disabling local browser access. No new cloud upload/inference
was needed for this revision. Existing local and cloud waveform samples in the
reported run contain the 880 Hz alarm around -15 dBFS at video second 7.

## Latest UI, limits and progress revision

Current full suites: 42 Python tests and 5 JavaScript tests pass. Earlier counts
are historical. Extra sound controls/browser-tone fallback were removed at the
user's request; native controls remain. Source preservation still passes.

New failing tests first captured the missing 50-MB/20-minute defaults, decoded
limit enforcement, live frame counters, exact filename job name, moved region
reference, and updated link label. Tests now cover incomplete diagnostic rows,
isolation from previous attempts, changed counters across GET refreshes, percentage
calculation and background validation refusing over-limit recordings.

`environment.yml` pins Python 3.13.12, pip 25.3, FFmpeg upstream 8.0.1 and 75
packages from the installed dependency graph. Parsed YAML and all package pins
were checked against installed metadata. No fresh Conda environment was created.
Local browser automation remains disabled in Work settings, so this revision's
layout was checked through Streamlit render tests and controlled player geometry,
not a live browser screenshot. No new inference or cloud upload was needed.

SQLite reset: all four previous jobs had succeeded. Services were stopped, the
SQLite backup API created `data/backups/jobs-before-reset-20261113T123642Z.sqlite3`,
and its integrity check passed with four jobs preserved. The fresh registry has
zero jobs and zero uploads. Old run links now return 404. Media files and cloud
assets were retained. API/frontend health returned 200 after restart; the worker
reported ready. Effective runtime limits checked as 50 MB and 1,200 seconds.
SQLite 3.51.1 is also pinned in the environment file alongside Python/pip/FFmpeg.

## Manual status updates and production dependency audit

Status GET requests are now made only when the user clicks Check status or
Load run. Opening a saved URL, normal UI reruns and submission rendering do not
fetch status automatically. Streamlit's own UI connection and the worker's
local SQLite queue checks are separate from these status API requests.

The corrected request-count test reproduces the old saved-URL auto-fetch, and
passes against the revised UI. Full suite: 44 Python tests passed in 9.64 seconds;
5 JavaScript tests passed; pip check found no broken installed requirements.
An earlier suite invocation stalled and was stopped; the full fresh run above
completed. No runtime/model dependency was changed in the working environment.

The production environment now pins 71 runtime packages. Removed pytest,
iniconfig, pluggy and pygments; test tools remain in requirements-dev.txt.
The dependency audit test checks every remaining installed package's declared
non-extra dependencies and version constraints against the pinned list. Framework
requirements such as Streamlit's chart/map libraries remain installer requirements
although this app does not use those features. Removing their manifest lines alone
would not prevent installation. No fresh Conda environment/VM was created, so a
clean installation is not claimed as tested. Python/pip/FFmpeg/SQLite pins remain.
