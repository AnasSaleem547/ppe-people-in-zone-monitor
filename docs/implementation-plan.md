# Notebook Web Wrapper Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Test first;
> run and observe each failing group before implementing it. Commit each group.

**Goal:** Serve the unchanged CV techniques through a local FastAPI/Streamlit app.
**Architecture:** A small API persists uploads/jobs in SQLite. API background
threads validate video; a separately locked worker runs CV, adds sound and
uploads the completed result. Streamlit owns annotation and status display.
**Tech stack:** FastAPI, SQLite stdlib, Streamlit v2 components, PyAV, FFmpeg,
Ultralytics 8.4.37, Cloudinary Python SDK.
**Spec:** docs/approved-design.md

## Global constraints
- All deliverables live in codebase; no changes to original notebook/project.
- Source notebook: /home/anas/PPE_YOLO_continuity_finalister.ipynb.
- Core modules retain source bodies; only package imports differ.
- N positive integer; T finite positive; four ordered valid points inside image.
- Cell 13 evidence_mode/readable_labels/stable_ids all True; crop context False.
- Strict video time > T; audio follows notebook trigger/reset records.
- Three APIs, no v1; 7-second short-video polling; exact secret in ignored .env.

## Review focus
- A job submitted during validation must not start before a valid result.
- Different requests sharing an idempotency key must produce a conflict.
- Resized previews and nonzero/variable timestamps must stay aligned.
- Worker restart/upload retry must not falsely report success or mix artifacts.
- Uncertain occupancy must retain the existing audio/visual alarm policy.

## Task 1: CV preservation and configuration
Files: services/cv/*.py, services/pipeline.py, config.py, provenance/*,
tests/test_cv_contract.py, tests/test_pipeline.py, requirements*.txt.
Interfaces: Settings; PipelineRunner.run(path, polygon, n, seconds, output_root).
- [x] Write failing source-preservation, timer, adapter-call and rendering tests.
- [x] Run tests; observe missing implementation failures.
- [x] Extract seven modules, configuration and adapter with lazy model loading.
- [x] Run tests; commit with Codex co-author.

## Task 2: Persistent queue and background validation
Files: repository.py, schemas.py, services/media.py, tests/test_repository.py,
tests/test_media.py. Interfaces: Repository upload/job CRUD, claim/recovery;
inspect_video, validate_video, region_preview.
- [x] Write failing queue durability/claim/idempotency/validation-gate tests and
      real video timestamp/preview/invalid media tests.
- [x] Run tests; implement SQLite transactions and media handling; run suite.
- [x] Commit with Codex co-author.

## Task 3: API routes
Files: main.py, routes/*.py, tests/test_api.py.
Interfaces: create_app(settings), three routes, JSON with inline image previews.
- [x] Write failing upload/job/status tests including pending and failed validation,
      invalid coordinates, oversized upload, repeated key and unknown identifiers.
- [x] Run tests; implement routes and background-validator lifecycle; run suite.
- [x] Commit with Codex co-author.

## Task 4: Audio, cloud and worker
Files: services/alarms.py, services/cloud_storage.py, worker.py,
tests/test_alarms.py, tests/test_worker.py, tests/test_cloud.py.
Interfaces: build_intervals(report, endpoint); add_alarm_audio(...);
CloudStorage.upload(...); Worker.run_once().
- [x] Write failing trigger/reset/EOF tests, real FFmpeg waveform/timestamp tests,
      delivery-URL tests and checkpoint/retry/restart worker tests.
- [x] Run tests; implement independent postprocessing and single-worker queue loop.
- [x] Run suite; commit with Codex co-author.

## Task 5: Streamlit UI and documentation
Files: frontend/app.py, frontend/api_client.py, frontend/annotation.py,
frontend/annotation.js, tests/test_frontend.py, tests/annotation.test.mjs, README.md.
Interfaces: JS canvas ↔ original-coordinate points; Python API client; UI state.
- [x] Write/run failing coordinate, component-event and API client/polling tests.
- [x] Implement upload/annotation/status/result flow, region verification and audio
      playback. Document setup, env, worker operation and guarantees.
- [x] Run all tests, browser smoke, real short inference and authorized small
      Cloudinary integration test. Review full code and fix important findings
      test-first. Commit with Codex co-author.

## Progress
Approved implementation proceeds without another approval round.
Ruling: use a new Git repository inside codebase because its parent has no Git
repository and the user requested all implementation in that folder.

## Completion ledger

- Task 1 complete: six tests RED→GREEN; commit 59c9d87.
- Task 2 complete: nine additional tests RED→GREEN; commit cc2ed71.
- Task 3 complete: three API tests RED→GREEN; commit 6d511f7.
- Task 4 complete: seven tests RED→GREEN, real FFmpeg checks; commit d390b0c.
- Task 5 complete: frontend tests RED→GREEN, browser/cloud/model checks; commit 66425fe plus final verification commit.
- Final review: independent reviewer checked all modules and source preservation.
  Expiry/idempotency finding reproduced RED→GREEN. Optional fresh-worker restart
  coverage added to existing checkpoint test, requiring no production change.
- Final timing finding reproduced RED→GREEN; final-frame hold adjusted only in
  post-CV media packaging. Current tests: 33 Python + 3 JavaScript, all passing.
- Ruling: keep this standalone repository on feat/fastapi-streamlit, without a
  remote or integration branch. The parent is not a repository. Cost if wrong:
  Git history can later be imported into the intended repository.
- Ruling: use API port 8010 because 8000 is occupied by an unrelated service.
  Cost if wrong: change API_BASE_URL and the launch command together.
- Ruling: retain the original CV writer and restore final-frame hold in audio
  packaging using validated source timing. Cost/limit: when final frame duration
  is missing, the last frame spacing or nominal rate is an estimate. No claim
  of universal delivery timing equivalence after Cloudinary conversion.
- No deferred reviewer findings remain. No code was pushed or published as a site.
